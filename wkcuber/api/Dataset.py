from shutil import rmtree
from abc import ABC, abstractmethod
from os import mkdir
from os.path import join, normpath, basename
from pathlib import Path
import numpy as np
from os import path

from wkcuber.api.Properties import WKProperties, TiffProperties
from wkcuber.api.Layer import Layer, WKLayer, TiffLayer


class AbstractDataset(ABC):
    @abstractmethod
    def __init__(self, properties):
        self.layers = {}
        self.path = Path(properties.path).parent
        self.properties = properties

        # construct self.layer
        for layer_name in self.properties.data_layers:
            layer = self.properties.data_layers[layer_name]
            self.add_layer(
                layer.name, layer.category, layer.element_class, layer.num_channels
            )
            for resolution in layer.wkw_resolutions:
                self.layers[layer_name].setup_mag(resolution.mag.to_layer_name())

    @classmethod
    @abstractmethod
    def open(cls, dataset_path):
        pass

    @classmethod
    def create_with_properties(cls, properties):
        # initialize object
        dataset = cls(properties)
        # create directories on disk and write datasource-properties.json
        try:
            mkdir(dataset.path)
            dataset.properties.export_as_json()
        except OSError:
            raise FileExistsError("Creation of Dataset {} failed".format(dataset.path))

        return dataset

    @classmethod
    @abstractmethod
    def create(cls, dataset_path, scale):
        pass

    def downsample(self, layer, target_mag_shape, source_mag):
        raise NotImplemented()

    def get_properties(self):
        return self.properties

    def get_layer(self, layer_name) -> Layer:
        if layer_name not in self.layers.keys():
            raise IndexError(
                "The layer {} is not a layer of this dataset".format(layer_name)
            )
        return self.layers[layer_name]

    def add_layer(self, layer_name, category, dtype=np.dtype("uint8"), num_channels=1):
        # normalize the value of dtype in case the parameter was passed as a string
        dtype = np.dtype(dtype)

        if layer_name in self.layers.keys():
            raise IndexError(
                "Adding layer {} failed. There is already a layer with this name".format(
                    layer_name
                )
            )
        self.layers[layer_name] = self.__create_layer__(layer_name, dtype, num_channels)
        self.properties.add_layer(layer_name, category, dtype.name, num_channels)
        return self.layers[layer_name]

    def get_or_add_layer(
        self, layer_name, category, dtype=np.dtype("uint8"), num_channels=1
    ):
        if layer_name in self.layers.keys():
            assert self.properties.data_layers[layer_name].category == category, (
                "Cannot get_or_add_layer: The layer %s already exists, but the dytpes do not match"
                % layer_name
            )
            assert self.layers[layer_name].dtype == np.dtype(dtype), (
                "Cannot get_or_add_layer: The layer %s already exists, but the dytpes do not match"
                % layer_name
            )
            assert self.layers[layer_name].num_channels == num_channels, (
                "Cannot get_or_add_layer: The layer %s already exists, but the number of channels do not match"
                % layer_name
            )
            return self.layers[layer_name]
        else:
            return self.add_layer(layer_name, category, dtype, num_channels)

    def delete_layer(self, layer_name):
        if layer_name not in self.layers.keys():
            raise IndexError(
                "Removing layer {} failed. There is no layer with this name".format(
                    layer_name
                )
            )
        del self.layers[layer_name]
        self.properties.delete_layer(layer_name)
        # delete files on disk
        rmtree(join(self.path, layer_name))

    def get_slice(
        self, layer_name, mag_name, size=(1024, 1024, 1024), global_offset=(0, 0, 0)
    ):
        layer = self.get_layer(layer_name)
        mag = layer.get_mag(mag_name)
        mag_file_path = path.join(self.path, layer.name, mag.name)

        return mag.get_slice(mag_file_path, size=size, global_offset=global_offset)

    def __create_layer__(self, layer_name, dtype, num_channels):
        raise NotImplementedError


class WKDataset(AbstractDataset):
    @classmethod
    def open(cls, dataset_path):
        properties = WKProperties.from_json(
            join(dataset_path, "datasource-properties.json")
        )
        return cls(properties)

    @classmethod
    def create(cls, dataset_path, scale):
        name = basename(normpath(dataset_path))
        properties = WKProperties(
            join(dataset_path, "datasource-properties.json"), name, scale
        )
        return WKDataset.create_with_properties(properties)

    def __init__(self, properties):
        super().__init__(properties)
        assert isinstance(properties, WKProperties)

    def to_tiff_dataset(self, new_dataset_path):
        raise NotImplementedError  # TODO; implement

    def __create_layer__(self, layer_name, dtype, num_channels):
        return WKLayer(layer_name, self, dtype, num_channels)


class TiffDataset(AbstractDataset):
    @classmethod
    def open(cls, dataset_path):
        properties = TiffProperties.from_json(
            join(dataset_path, "datasource-properties.json")
        )
        return cls(properties)

    @classmethod
    def create(cls, dataset_path, scale, pattern="{z}.tif"):
        name = basename(normpath(dataset_path))
        properties = TiffProperties(
            join(dataset_path, "datasource-properties.json"),
            name,
            scale,
            pattern=pattern,
            tile_size=None,
        )
        return TiffDataset.create_with_properties(properties)

    @classmethod
    def create_tiled(cls, dataset_path, scale, tile_size, pattern="{z}.tif"):
        name = basename(normpath(dataset_path))
        properties = TiffProperties(
            join(dataset_path, "datasource-properties.json"),
            name,
            scale,
            pattern=pattern,
            tile_size=tile_size,
        )
        return TiffDataset.create_with_properties(properties)

    def __init__(self, properties):
        super().__init__(properties)
        assert isinstance(properties, TiffProperties)

    def to_wk_dataset(self, new_dataset_path):
        raise NotImplementedError  # TODO; implement

    def __create_layer__(self, layer_name, dtype, num_channels):
        return TiffLayer(layer_name, self, dtype, num_channels)

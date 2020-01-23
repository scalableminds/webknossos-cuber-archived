import json
import numpy as np
from os.path import join, dirname, isfile

from wkw import wkw

from wkcuber.mag import Mag


def extract_num_channels(num_channels_in_properties, path, layer, mag):
    # if a wk dataset is not created with this API, then it most likely doesn't have the attribute 'num_channels' in the
    # datasource-properties.json. In this case we need to extract the 'num_channels' from the 'header.wkw'.
    if num_channels_in_properties is None:
        wkw_ds_file_path = join(dirname(path), layer, str(mag["resolution"]))
        if not isfile(join(wkw_ds_file_path, "header.wkw")):
            raise Exception(
                f"The dataset you are trying to open does not have the attribute 'num_channels' for layer {layer}. "
                f"However, this attribute is necessary. To mitigate this problem, it was tried to locate "
                f"the file {wkw_ds_file_path} to extract the num_channels from there. "
                f"Since this file does not exist, the attempt to open the dataset failed."
                f"Please add the attribute manually to solve the problem. "
                f"If the layer does not contains any data, you can also delete the layer and add it again.")
        return extract_num_channels_from_wkw_header(wkw_ds_file_path)
    else:
        return num_channels_in_properties


def extract_num_channels_from_wkw_header(wkw_ds_file_path):
    wkw_ds = wkw.Dataset.open(wkw_ds_file_path)
    return wkw_ds.header.num_channels


class Resolution:
    def _to_json(self) -> dict:
        pass

    @classmethod
    def _from_json(cls, json_data):
        pass


class TiffResolution(Resolution):
    def __init__(self, mag):
        self._mag = Mag(mag)

    def _to_json(self) -> dict:
        return {"resolution": self.mag.to_array()}

    @classmethod
    def _from_json(cls, json_data):
        return cls(json_data["resolution"])

    @property
    def mag(self) -> Mag:
        return self._mag


class WkResolution(Resolution):
    def __init__(self, mag, cube_length):
        self._mag = Mag(mag)
        self._cube_length = cube_length

    def _to_json(self) -> dict:
        return {"resolution": self.mag.to_array(), "cubeLength": self.cube_length}

    @classmethod
    def _from_json(cls, json_data):
        return cls(json_data["resolution"], json_data["cubeLength"])

    @property
    def mag(self) -> Mag:
        return self._mag

    @property
    def cube_length(self) -> int:
        return self._cube_length


class Properties:

    FILE_NAME = "datasource-properties.json"

    def __init__(self, path, name, scale, team="", data_layers=None):
        self._path = path
        self._name = name
        self._team = team
        self._scale = scale
        if data_layers is None:
            self._data_layers = {}
        else:
            self._data_layers = data_layers

    @classmethod
    def _from_json(cls, path):
        pass

    def _export_as_json(self):
        pass

    def _add_layer(self, layer_name, category, element_class, num_channels=1):
        # this layer is already in data_layers in case we reconstruct the dataset from a datasource-properties.json
        if layer_name not in self.data_layers:
            new_layer = LayerProperties(
                layer_name, category, element_class, num_channels
            )
            self.data_layers[layer_name] = new_layer
            self._export_as_json()

    def _delete_layer(self, layer_name):
        del self.data_layers[layer_name]
        self._export_as_json()

    def _delete_mag(self, layer_name, mag):
        self._data_layers[layer_name]._delete_resolution(mag)
        self._export_as_json()

    def _set_bounding_box_of_layer(self, layer_name, offset, size):
        self._data_layers[layer_name]._set_bounding_box_size(size)
        self._data_layers[layer_name]._set_bounding_box_offset(offset)
        self._export_as_json()

    @property
    def name(self) -> str:
        return self._name

    @property
    def path(self) -> str:
        return self._path

    @property
    def team(self) -> str:
        return self._team

    @property
    def scale(self) -> tuple:
        return self._scale

    @property
    def data_layers(self) -> dict:
        return self._data_layers


class WKProperties(Properties):
    @classmethod
    def _from_json(cls, path) -> Properties:
        with open(path) as datasource_properties:
            data = json.load(datasource_properties)

            # reconstruct data_layers
            data_layers = {}
            for layer in data["dataLayers"]:
                data_layers[layer["name"]] = LayerProperties._from_json(
                    layer, WkResolution, path
                )

            return cls(
                path, data["id"]["name"], data["scale"], data["id"]["team"], data_layers
            )

    def _export_as_json(self):
        data = {
            "id": {"name": self.name, "team": self.team},
            "scale": self.scale,
            "dataLayers": [
                self.data_layers[layer_name]._to_json()
                for layer_name in self.data_layers
            ],
        }
        with open(self.path, "w") as outfile:
            json.dump(data, outfile, indent=4, separators=(",", ": "))

    def _add_mag(self, layer_name, mag, cube_length):
        # this mag is already in wkw_magnifications in case we reconstruct the dataset from a datasource-properties.json
        if not any(
            [
                res.mag == Mag(mag)
                for res in self.data_layers[layer_name].wkw_magnifications
            ]
        ):
            self._data_layers[layer_name]._add_resolution(
                WkResolution(mag, cube_length)
            )
            self._export_as_json()


class TiffProperties(Properties):
    def __init__(
        self,
        path,
        name,
        scale,
        pattern,
        team="",
        data_layers=None,
        grid_shape=(0, 0),
        tile_size=(32, 32),
    ):
        super().__init__(path, name, scale, team, data_layers)
        self._grid_shape = grid_shape
        self.pattern = pattern
        self.tile_size = tile_size

    @classmethod
    def _from_json(cls, path) -> Properties:
        with open(path) as datasource_properties:
            data = json.load(datasource_properties)

            # reconstruct data_layers
            data_layers = {}
            for layer in data["dataLayers"]:
                data_layers[layer["name"]] = LayerProperties._from_json(
                    layer, TiffResolution, path
                )

            return cls(
                path=path,
                name=data["id"]["name"],
                scale=data["scale"],
                pattern=data["pattern"],
                team=data["id"]["team"],
                data_layers=data_layers,
                grid_shape=data["grid_shape"],
                tile_size=data.get("tile_size"),
            )

    def _export_as_json(self):
        data = {
            "id": {"name": self.name, "team": self.team},
            "scale": self.scale,
            "pattern": self.pattern,
            "dataLayers": [
                self.data_layers[layer_name]._to_json()
                for layer_name in self.data_layers
            ],
            "grid_shape": self.grid_shape,
            "tile_size": {} if self.tile_size is None else self.tile_size,
        }
        with open(self.path, "w") as outfile:
            json.dump(data, outfile, indent=4, separators=(",", ": "))

    @property
    def grid_shape(self) -> tuple:
        return self._grid_shape

    def _add_mag(self, layer_name, mag):
        # this mag is already in wkw_magnifications in case we reconstruct the dataset from a datasource-properties.json
        if not any(
            [
                res.mag == Mag(mag)
                for res in self.data_layers[layer_name].wkw_magnifications
            ]
        ):
            self.data_layers[layer_name]._add_resolution(TiffResolution(mag))
            self._export_as_json()


class LayerProperties:
    def __init__(
        self,
        name,
        category,
        element_class,
        num_channels,
        bounding_box=None,
        resolutions=None,
    ):
        self._name = name
        self._category = category
        self._element_class = element_class
        self._num_channels = num_channels
        self._bounding_box = bounding_box or {
            "topLeft": (-1, -1, -1),
            "width": 0,
            "height": 0,
            "depth": 0,
        }
        self._wkw_magnifications = resolutions or []

    def _to_json(self):
        return {
            "name": self.name,
            "category": self.category,
            "elementClass": self.element_class,
            "num_channels": self.num_channels,
            "boundingBox": {}
            if self.bounding_box is None
            else {
                "topLeft": self.bounding_box["topLeft"],
                "width": self.bounding_box["width"],
                "height": self.bounding_box["height"],
                "depth": self.bounding_box["depth"],
            },
            "wkwResolutions": [r._to_json() for r in self.wkw_magnifications],
        }

    @classmethod
    def _from_json(cls, json_data, resolution_type, dataset_path):
        # create LayerProperties without resolutions
        layer_properties = cls(
            json_data["name"],
            json_data["category"],
            json_data["elementClass"],
            extract_num_channels(json_data.get("num_channels"), dataset_path, json_data["name"], json_data["wkwResolutions"][0]),
            json_data["boundingBox"],
        )

        # add resolutions to LayerProperties
        for resolution in json_data["wkwResolutions"]:
            layer_properties._add_resolution(resolution_type._from_json(resolution))

        return layer_properties

    def _add_resolution(self, resolution):
        self._wkw_magnifications.append(resolution)

    def _delete_resolution(self, resolution):
        self._wkw_magnifications.delete(resolution)

    def get_bounding_box_size(self) -> tuple:
        return (
            self.bounding_box["width"],
            self.bounding_box["height"],
            self.bounding_box["depth"],
        )

    def get_bounding_box_offset(self) -> tuple:
        return tuple(self.bounding_box["topLeft"])

    def _set_bounding_box_size(self, size):
        self._bounding_box["width"] = size[0]
        self._bounding_box["height"] = size[1]
        self._bounding_box["depth"] = size[2]

    def _set_bounding_box_offset(self, offset):
        self._bounding_box["topLeft"] = offset

    @property
    def name(self) -> str:
        return self._name

    @property
    def category(self) -> str:
        return self._category

    @property
    def element_class(self):
        return self._element_class

    @property
    def num_channels(self) -> int:
        return self._num_channels

    @property
    def bounding_box(self) -> dict:
        return self._bounding_box

    @property
    def wkw_magnifications(self) -> dict:
        return self._wkw_magnifications

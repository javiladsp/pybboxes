import warnings
from abc import ABC, abstractmethod
from typing import List, Tuple, Union

import numpy as np

from pybboxes.utils import find_stack_level

NORMALIZED_BOXES = ["albumentations", "fiftyone", "yolo"]


class Box:
    def __init__(self, x_tl: int, y_tl: int, x_br: int, y_br: int):
        self.x_tl = x_tl
        self.y_tl = y_tl
        self.x_br = x_br
        self.y_br = y_br

    def __add__(self, other: "Box") -> int:
        return self.union(other)

    def __sub__(self, other: "Box") -> int:
        return int(self.area - self.intersection(other))

    def __mul__(self, other: "Box") -> int:
        return self.intersection(other)

    def __truediv__(self, other: "Box") -> float:
        return self.area / other.area

    @property
    def area(self) -> int:
        return self.width * self.height

    @property
    def height(self) -> int:
        return int(self.y_br - self.y_tl)

    @property
    def width(self) -> int:
        return int(self.x_br - self.x_tl)

    def intersection(self, other: "Box") -> int:
        x_tl, y_tl = np.maximum((self.x_tl, self.y_tl), (other.x_tl, other.y_tl))
        x_br, y_br = np.minimum((self.x_br, self.y_br), (other.x_br, other.y_br))
        if x_tl >= x_br or y_tl >= y_br:
            return 0
        intersection_width = x_br - x_tl
        intersection_height = y_br - y_tl
        return int(intersection_width * intersection_height)

    def union(self, other: "Box") -> int:
        return int(self.area + other.area - self.intersection(other))

    def iou(self, other: "Box") -> float:
        return self.intersection(other) / self.union(other)

    def is_inside_of(self, other: "Box", tolerance: float = 0.0) -> bool:
        """
        Check if the current box is inside another box with an optional tolerance.

        Parameters:
        other (Box): The parent box to check against.
        tolerance (float): A percentage (0.0 to 1.0) of the parent box size to allow as margin of error.
                           For example, a tolerance of 0.1 allows a 10% margin of error.

        Returns:
        bool: True if the current box is inside the adjusted parent box, False otherwise.

        Usage:
        >>> A = Box(10, 10, 65, 65)
        >>> B = Box(0, 0, 60, 60)
        >>> A.is_inside_of(B, tolerance=0.0)
        False
        >>> A.is_inside_of(B, tolerance=0.1)
        True

        In this example, the tolerance of 0.1 (10%) allows the parent box B to be expanded by 10% of its size
        in all directions, making it possible for the child box A to be considered inside B even though it
        slightly exceeds the original boundaries of B.
        """
        tolerance_x = (other.x_br - other.x_tl) * tolerance
        tolerance_y = (other.y_br - other.y_tl) * tolerance

        adjusted_x_tl = max(0, other.x_tl - tolerance_x)
        adjusted_y_tl = max(0, other.y_tl - tolerance_y)
        adjusted_x_br = other.x_br + tolerance_x
        adjusted_y_br = other.y_br + tolerance_y

        return (self.x_tl >= adjusted_x_tl and
                self.y_tl >= adjusted_y_tl and
                self.x_br <= adjusted_x_br and
                self.y_br <= adjusted_y_br)


class BaseBoundingBox(Box, ABC):
    def __init__(
        self,
        v1: Union[int, float],
        v2: Union[int, float],
        v3: Union[int, float],
        v4: Union[int, float],
        image_size: Tuple[int, int] = None,
        strict: bool = False,
    ):
        self._image_size = image_size
        self.strict = strict
        self._is_oob = None
        self._validate_and_set_values(v1, v2, v3, v4)
        voc_values = self.to_voc(return_values=True)
        super(BaseBoundingBox, self).__init__(*voc_values)

    def __repr__(self):
        image_width, image_height = self.image_size
        str_vals = " ".join([f"{v:.4f}" if isinstance(v, float) else str(v) for v in self.values])
        return f"<[{str_vals}] ({self.width}x{self.height}) | Image: " f"({image_width or '?'}x{image_height or '?'})>"

    @property
    def is_oob(self) -> Union[bool, None]:
        """
        Whether the box is OOB (Out-of-bounds).

        Returns:
            None -> unknown. False -> Not OOB. True -> OOB.
        """
        return self._is_oob

    @property
    def image_size(self):
        if self._image_size is not None:
            return self._image_size
        else:
            return None, None

    @image_size.setter
    def image_size(self, image_size: Tuple[int, int]):
        self._image_size = image_size

    def is_image_size_null(self):
        if self.image_size == (None, None):
            return True
        return False

    @property
    def values(self) -> Tuple:
        return self._values

    def _correct_value_types(self, *values) -> Tuple:
        return values

    @abstractmethod
    def _validate_values(self, *values):
        pass

    def _set_values(self, *values):
        """
        This method is intended to be "final", and should not be overridden in child classes.
        """
        self._values = values

    def _validate_and_set_values(self, *values) -> None:
        """
        Validate and sets given values if validation is successful.
        """
        self.raw_values = values
        values = self._correct_value_types(*values)
        self._validate_values(*values)
        self._set_values(*values)

    def to_albumentations(self, return_values: bool = False) -> Union[Tuple[int, int, int, int], "BaseBoundingBox"]:
        return self.to_voc().to_albumentations(return_values)

    def to_coco(self, return_values: bool = False) -> Union[Tuple[int, int, int, int], "BaseBoundingBox"]:
        return self.to_voc().to_coco(return_values)

    def to_fiftyone(self, return_values: bool = False) -> Union[Tuple[int, int, int, int], "BaseBoundingBox"]:
        return self.to_voc().to_fiftyone(return_values)

    @abstractmethod
    def to_voc(self, return_values: bool = False) -> Union[Tuple[int, int, int, int], "BaseBoundingBox"]:
        pass

    def to_yolo(self, return_values: bool = False) -> Union[Tuple[int, int, int, int], "BaseBoundingBox"]:
        return self.to_voc().to_yolo(return_values)

    @property
    def name(self):
        return self.__class__.__name__.lower().replace("boundingbox", "")

    def _generic_operation(self, op: str, *args, **kwargs) -> None:
        refined_box = self.to_voc()
        box_op = getattr(refined_box, op)
        refined_box = box_op(*args, **kwargs)
        box_conversion = getattr(refined_box, f"to_{self.name}")
        refined_box = box_conversion()

        self.__init__(*refined_box.values, image_size=self.image_size, strict=self.strict)

    def clamp(self) -> "BaseBoundingBox":
        """
        Clamps the box with respect to the image borders. If the box is not OOB, does nothing.
        """
        self._generic_operation("clamp")
        return self

    def scale(self, factor: float) -> "BaseBoundingBox":
        self._generic_operation("scale", factor)
        return self

    def shift(self, amount: Tuple) -> "BaseBoundingBox":
        """
        Perform a shift operation on the bounding box inplace.

        Args:
            amount: The amount to shift the bounding box. The first value is the
                amount to shift the x-coordinate, and the second value is the
                amount to shift the y-coordinate.
        """
        if self.name in NORMALIZED_BOXES:
            width, height = self.image_size
            amount = (amount[0] * width, amount[1] * height)
        self._generic_operation("shift", amount)
        return self

    @classmethod
    @abstractmethod
    def from_voc(
        cls,
        x_tl: int,
        y_tl: int,
        x_br: int,
        y_br: int,
        image_size: Tuple[int, int] = None,
        strict: bool = True,
    ) -> "BaseBoundingBox":
        pass

    @classmethod
    def from_array_vectorize(cls, ar: np.ndarray):
        constructor = cls.from_array
        vconstructor = np.vectorize(constructor)
        return vconstructor(ar)

    @classmethod
    def from_array(cls, ar: Union[Tuple, List, np.ndarray], **kwargs) -> Union[np.ndarray, "BaseBoundingBox"]:
        """
        Takes input values containing at least a single bbox values. Input can be multidimensional
        array as long as the last dimension (-1) has length of 4, i.e for any array as input, the shape
        should look like (x,y,z,4) and the output is of shape (x,y,z).

        Args:
            ar: Input values as a tuple or array. If the input is an array, the dimension is preserved as is
                and each bounding box values is converted to the `BoundingBox` object.
            **kwargs: Additional keyword arguments for construction, see :py:meth:`BoundingBox.__init__`

        Notes:
            This method is intended to be "final", and should not be overridden in child classes.

        Returns:
            Either a `BoundingBox` object constructed from input values or list of `BoundingBox` objects
            as an array.
        """
        if not isinstance(ar, np.ndarray):
            ar = np.array(ar)
        if ar.shape[-1] != 4:
            raise ValueError(f"Given input array must have bounding box values at dim -1 as 4, got shape {ar.shape}.")
        if ar.ndim == 1:
            return cls(*ar, **kwargs)
        vf = np.vectorize(cls.from_array, signature="(n) -> ()", excluded={"image_size", "strict"})
        return vf(ar, **kwargs)

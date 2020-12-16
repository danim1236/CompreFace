#  Copyright (c) 2020 the original author or authors
# 
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
# 
#       https://www.apache.org/licenses/LICENSE-2.0
# 
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
#  or implied. See the License for the specific language governing
#  permissions and limitations under the License.

import os
import logging
from typing import List, Tuple

import attr
import numpy as np
from cached_property import cached_property
from insightface.app import FaceAnalysis
from insightface.model_zoo import model_zoo, model_store, face_recognition, face_detection
from insightface.utils import face_align

from src.constants import ENV
from src.services.dto.bounding_box import BoundingBoxDTO
from src.services.dto.scanned_face import ScannedFace
from src.services.facescan.imgscaler.imgscaler import ImgScaler
from src.services.facescan.scanner.facescanner import FaceScanner
from src.services.imgtools.types import Array3D

logger = logging.getLogger(__name__)


def _get_model_file(name):
    """ Return location for the pretrained on local file system.
    InsightFace `get_model_file` works only with build in models. 
    """
    root = os.path.expanduser(os.path.join('~', '.insightface', 'models'))
    dir_path = os.path.join(root, name)
    return model_store.find_params_file(dir_path)


@attr.s(auto_attribs=True, frozen=True)
class InsightFaceBoundingBox(BoundingBoxDTO):
    landmark: Tuple[int, ...]

    @property
    def dto(self):
        return BoundingBoxDTO(x_min=self.x_min, x_max=self.x_max,
                              y_min=self.y_min, y_max=self.y_max,
                              probability=self.probability)

    def scaled(self, coefficient: float) -> 'InsightFaceBoundingBox':
        # noinspection PyTypeChecker
        return InsightFaceBoundingBox(x_min=self.x_min * coefficient, x_max=self.x_max * coefficient,
                                      y_min=self.y_min * coefficient, y_max=self.y_max * coefficient,
                                      probability=self.probability,
                                      landmark=self.landmark * coefficient)


class DetectionOnlyFaceAnalysis(FaceAnalysis):
    rec_model = None
    ga_model = None

    def __init__(self, det_name):
        try:
            self.det_model = model_zoo.get_model(det_name)
        except ValueError:
            file = _get_model_file(det_name)
            self.det_model = face_detection.FaceDetector(file, 'net3')


class InsightFace(FaceScanner):
    ID = 'InsightFace'
    DETECTION_MODEL_NAME = ENV.DETECTION_MODEL
    CALCULATION_MODEL_NAME = ENV.CALCULATION_MODEL
    IMG_LENGTH_LIMIT = ENV.IMG_LENGTH_LIMIT

    _CTX_ID = ENV.GPU_ID
    # detection settings
    _NMS = 0.4
    det_prob_threshold = 0.8

    @cached_property
    def _detection_model(self):
        model = DetectionOnlyFaceAnalysis(self.DETECTION_MODEL_NAME)
        model.prepare(ctx_id=self._CTX_ID, nms=self._NMS)
        return model

    @cached_property
    def _calculation_model(self):
        name = self.CALCULATION_MODEL_NAME
        try:
            model = model_zoo.get_model(name)
        except ValueError:
            file = _get_model_file(name)
            model = face_recognition.FaceRecognition(name, True, file)
        model.prepare(ctx_id=self._CTX_ID)
        return model

    def scan(self, img: Array3D, det_prob_threshold: float = None) -> List[ScannedFace]:
        scanned_faces = []
        for box in self.find_faces(img, det_prob_threshold):
            face_img = face_align.norm_crop(img, landmark=box.landmark)
            embedding = self._calculation_model.get_embedding(face_img).flatten()
            scanned_faces.append(ScannedFace(box=box, embedding=embedding,
                                             img=img, face_img=face_img))
        return scanned_faces

    def find_faces(self, img: Array3D, det_prob_threshold: float = None) -> List[InsightFaceBoundingBox]:
        if det_prob_threshold is None:
            det_prob_threshold = self.det_prob_threshold
        assert 0 <= det_prob_threshold <= 1
        scaler = ImgScaler(self.IMG_LENGTH_LIMIT)
        img = scaler.downscale_img(img)
        results = self._detection_model.get(img, det_thresh=det_prob_threshold)
        boxes = []
        for result in results:
            downscaled_box_array = result.bbox.astype(np.int).flatten()
            downscaled_box = InsightFaceBoundingBox(x_min=downscaled_box_array[0],
                                                    y_min=downscaled_box_array[1],
                                                    x_max=downscaled_box_array[2],
                                                    y_max=downscaled_box_array[3],
                                                    probability=result.det_score,
                                                    landmark=result.landmark)
            box = downscaled_box.scaled(scaler.upscale_coefficient)
            if box.probability <= det_prob_threshold:
                logger.debug(f'Box Filtered out because below threshold ({det_prob_threshold}: {box})')
                continue
            logger.debug(f"Found: {box.dto}")
            boxes.append(box)
        return boxes

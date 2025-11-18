"""Model loading and caching utilities"""

import logging
from typing import Optional, Dict, Any
from enum import Enum

from .damage_detection import DamageDetectionPipeline, DamageDetectionConfig

logger = logging.getLogger(__name__)


class ModelType(str, Enum):
    """Supported model types"""
    DAMAGE_DETECTION = "damage_detection"
    MATERIAL_DETECTION = "material_detection"
    VOLUME_ESTIMATION = "volume_estimation"


class ModelLoader:
    """
    Singleton model loader for managing AI model instances.
    Implements model caching and lazy loading.
    """

    _instance: Optional["ModelLoader"] = None
    _models: Dict[ModelType, Any] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ModelLoader, cls).__new__(cls)
            cls._instance._models = {}
            logger.info("Initialized ModelLoader singleton")
        return cls._instance

    def get_damage_detection_pipeline(
        self, config: Optional[DamageDetectionConfig] = None
    ) -> DamageDetectionPipeline:
        """
        Get or create damage detection pipeline instance.

        Args:
            config: Optional configuration for pipeline

        Returns:
            DamageDetectionPipeline instance
        """
        if ModelType.DAMAGE_DETECTION not in self._models:
            logger.info("Creating new DamageDetectionPipeline instance")
            pipeline = DamageDetectionPipeline(config)
            pipeline.load_models()
            self._models[ModelType.DAMAGE_DETECTION] = pipeline
            logger.info("DamageDetectionPipeline loaded and cached")
        else:
            logger.debug("Using cached DamageDetectionPipeline instance")

        return self._models[ModelType.DAMAGE_DETECTION]

    def unload_model(self, model_type: ModelType):
        """
        Unload a specific model from cache.

        Args:
            model_type: Type of model to unload
        """
        if model_type in self._models:
            del self._models[model_type]
            logger.info(f"Unloaded {model_type.value} model from cache")

    def unload_all_models(self):
        """Unload all cached models"""
        self._models.clear()
        logger.info("Unloaded all models from cache")

    def get_loaded_models(self) -> list:
        """Get list of currently loaded model types"""
        return list(self._models.keys())

    def get_model_stats(self) -> Dict[str, Any]:
        """Get statistics for all loaded models"""
        stats = {}

        for model_type, model in self._models.items():
            if hasattr(model, "get_stats"):
                stats[model_type.value] = model.get_stats()

        return stats


# Global model loader instance
model_loader = ModelLoader()

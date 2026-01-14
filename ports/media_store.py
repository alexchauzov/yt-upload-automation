"""Interface for media file workflow management."""
from __future__ import annotations

from abc import ABC, abstractmethod

from domain.models import MediaStage


class MediaStore(ABC):
    """
    Media store interface for managing video file lifecycle through workflow stages.

    Domain knows only logical stages (IN_PROGRESS, UPLOADED), not physical locations.
    Implementation is responsible for mapping stages to storage locations.
    """

    @abstractmethod
    def transition(self, media_ref: str, to_stage: MediaStage) -> str:
        """
        Transition media file to a new workflow stage.

        Args:
            media_ref: Current media reference (implementation-specific identifier).
            to_stage: Target workflow stage.

        Returns:
            New media reference after transition.

        Raises:
            AdapterError: If transition fails (file not found, permission denied, etc).
        """
        pass

import os
import threading
from typing import Dict, Optional, Tuple
from app.ai.exceptions import InvalidPrompt
from app.ai.schemas.prompt_metadata import PromptTemplate
from app.ai.prompts.loader import load_prompt_file
import structlog

logger = structlog.get_logger()

class PromptRegistry:
    """Registry to load, store, version, and retrieve PromptTemplates."""

    def __init__(self):
        # Maps (category, name) -> {version_str: PromptTemplate}
        self._prompts: Dict[Tuple[str, str], Dict[str, PromptTemplate]] = {}
        self._lock = threading.Lock()

    def register_prompt(self, category: str, template: PromptTemplate) -> None:
        """Register a PromptTemplate in-memory.

        Args:
            category: The category folder (e.g. 'resume', 'interview').
            template: The PromptTemplate instance.
        """
        normalized_category = category.lower().strip()
        name = template.metadata.name.lower().strip()
        version = template.metadata.version.strip()

        key = (normalized_category, name)
        with self._lock:
            if key not in self._prompts:
                self._prompts[key] = {}
            self._prompts[key][version] = template

        logger.debug(
            "registered_prompt",
            category=normalized_category,
            name=name,
            version=version
        )

    def get_prompt(self, category: str, name: str, version: Optional[str] = None) -> PromptTemplate:
        """Retrieve a registered PromptTemplate.

        Args:
            category: The prompt category.
            name: The prompt name.
            version: Optional version to retrieve. If None, resolves the latest version.

        Returns:
            The matching PromptTemplate.

        Raises:
            InvalidPrompt: If prompt or version is not found in the registry.
        """
        normalized_category = category.lower().strip()
        normalized_name = name.lower().strip()
        key = (normalized_category, normalized_name)

        if key not in self._prompts or not self._prompts[key]:
            raise InvalidPrompt(
                f"Prompt '{name}' under category '{category}' not found in registry."
            )

        versions_dict = self._prompts[key]

        if version:
            if version not in versions_dict:
                raise InvalidPrompt(
                    f"Prompt '{name}' under category '{category}' with version '{version}' not found."
                )
            return versions_dict[version]

        # Resolve latest version
        def version_key(v_str: str) -> Tuple[int, ...]:
            parts = []
            for part in v_str.split("."):
                try:
                    parts.append(int(part))
                except ValueError:
                    parts.append(0)
            return tuple(parts)

        latest_version = max(versions_dict.keys(), key=version_key)
        return versions_dict[latest_version]

    def load_from_directory(self, directory_path: str) -> None:
        """Scan directory recursively, loading files under subdirectories as category prompts.

        Args:
            directory_path: Root template directory.
        """
        if not os.path.exists(directory_path):
            logger.warning("prompt_directory_not_found", path=directory_path)
            return

        for root, _, files in os.walk(directory_path):
            for file in files:
                if file.endswith((".jinja", ".txt", ".yaml", ".html")):
                    filepath = os.path.join(root, file)
                    rel_dir = os.path.relpath(root, directory_path)
                    if rel_dir == ".":
                        category = "shared"
                    else:
                        category = rel_dir.split(os.sep)[0]

                    try:
                        template = load_prompt_file(filepath)
                        self.register_prompt(category, template)
                    except Exception as e:
                        logger.error(
                            "failed_to_load_prompt_file",
                            filepath=filepath,
                            error=str(e)
                        )
                        raise

    def clear(self) -> None:
        """Clear all registered prompts."""
        self._prompts.clear()

    def size(self) -> int:
        """Total number of registered templates (including different versions)."""
        return sum(len(versions) for versions in self._prompts.values())

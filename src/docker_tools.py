import logging

from pathlib import Path

import docker


def setup_logger(name: str, log_path: Path) -> logging.Logger:
    """Create or reuse a file logger for Docker build output.

    Args:
        name: Logger name and image identifier.
        log_path: Path to the log file.

    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    if logger.handlers:
        return logger
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)
    return logger


def build_image(
    image_name: str,
    dockerfile: str,
    build_dir: Path,
    platform: str = "linux/amd64",
    nocache: bool = False,
) -> None:
    """Build a Docker image from a Dockerfile string.

    Args:
        image_name: Tag for the built image.
        dockerfile: Dockerfile contents.
        build_dir: Directory used as build context.
        platform: Target platform string.
        nocache: Whether to disable build cache.
    """
    logger = setup_logger(image_name, build_dir / "build_image.log")
    dockerfile_path = build_dir / "Dockerfile"
    dockerfile_path.write_text(dockerfile, encoding="utf-8")
    client = docker.from_env()
    response = client.api.build(
        path=str(build_dir),
        tag=image_name,
        rm=True,
        forcerm=True,
        decode=True,
        platform=platform,
        nocache=nocache,
    )
    for chunk in response:
        if "stream" in chunk:
            logger.info(chunk["stream"].rstrip())
        elif "errorDetail" in chunk:
            raise RuntimeError(chunk["errorDetail"]["message"])

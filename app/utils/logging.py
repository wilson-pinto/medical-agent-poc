import logging
import os

def get_logger(name: str) -> logging.Logger:
    """
    Configures and returns a logger with a specific name.

    Args:
        name: The name of the logger, typically the module name.

    Returns:
        A configured logging.Logger instance.
    """
    # Create logger with a specific name
    logger = logging.getLogger(name)

    # Set the logging level from an environment variable, defaulting to INFO
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logger.setLevel(log_level)

    # Prevent duplicate handlers
    if not logger.handlers:
        # Create a console handler
        console_handler = logging.StreamHandler()
        # Create a formatter for the handler
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        # Set the formatter on the handler
        console_handler.setFormatter(formatter)
        # Add the handler to the logger
        logger.addHandler(console_handler)

    return logger

# Example usage (for demonstration, can be removed later)
if __name__ == "__main__":
    my_logger = get_logger("my_example_module")
    my_logger.info("This is an info message.")
    my_logger.warning("This is a warning message.")

# Contributing to infracents

Thank you for your interest in contributing! 🎉

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/YOUR_USERNAME/infracents.git`
3. Install dev dependencies: `pip install -e ".[dev]"`
4. Create a feature branch: `git checkout -b feature/your-feature-name`

## Development

```bash
# Run tests
pytest

# Lint
ruff check src/ tests/

# Type check
mypy src/
```

## Submitting Changes

1. Ensure all tests pass: `pytest`
2. Add tests for new functionality
3. Update the README if your change affects usage
4. Open a pull request with a clear description

## Good First Issues

Check the [issues tab](https://github.com/nirbhays/infracents/issues?q=label%3A%22good+first+issue%22) for beginner-friendly tasks.

## Code Style

- Follow existing patterns in the codebase
- Use type hints
- Keep functions focused and testable

## Questions?

Open an issue or reach out via the repository discussions.

# Contributing to red-willow

Thanks for your interest in contributing! Please follow these simple steps.

- Fork the repository and create a branch named `feature/your-feature` or `fix/your-bug`.
- Write clear commit messages and keep changes focused.
- Run the test suite locally before opening a PR:

  ```bash
  pip install -r requirements.txt
  pytest -q
  ```

- Ensure code is formatted with `black` and passes `flake8`.
- Install and enable `pre-commit` to run hooks locally:

  ```bash
  pip install pre-commit
  pre-commit install
  pre-commit run --all-files
  ```

- Open a pull request against `main`; include a brief description and link any related issues.

Maintainers will review and provide feedback. Thanks! 🙏

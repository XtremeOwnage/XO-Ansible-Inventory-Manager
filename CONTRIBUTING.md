# Contributing to Ansible Inventory Manager

First off, thank you for considering contributing to Ansible Inventory Manager! It's people like you that make this project such a great tool.

## How to Contribute

### Reporting Bugs

If you find a bug in the source code, you can help by submitting an issue to our [GitHub Issue Tracker](https://github.com/XtremeOwnage/XO-Ansible-Inventory-Manager/issues). Even better, you can submit a Pull Request with a fix.

### Suggesting Enhancements

If you have an idea for a new feature or enhancement, please feel free to create an issue with your suggestion.

### Submitting Pull Requests

1. Fork the repository on GitHub.
2. Create a new branch from `main` for your feature or bug fix.
3. Ensure your code follows the project's coding standards and passes all tests.
4. Submit a pull request to the main repository.

## Coding Standards

- Follow [PEP 8](https://pep8.org/) for Python code.
- Write meaningful commit messages.
- Include comments in your code.
- Write unit tests for new features and bug fixes.

## Running Tests

Before submitting your code, run the linter and the tests (see [docs/testing.md](docs/testing.md)):

```bash
pip install -r requirements-dev.txt
ruff check src tests
pytest
```

If you change the criteria language, update the operator tables in `docs/expression-syntax.md`; a test checks they match the code.

## License

By contributing to Ansible Inventory Manager, you agree that your contributions will be licensed under the [GNU GPLv3 License](LICENSE).
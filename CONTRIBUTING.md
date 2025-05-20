# Contributing to TextractSSMLProcessor

Thank you for your interest in contributing! The following guidelines should help you get started.

## Environment setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/TextractSSMLProcessor.git
   cd TextractSSMLProcessor
   ```
2. **Create and activate a Python environment** (Conda is recommended)
   ```bash
   conda create -n textract_ssml_processor python=3.8
   conda activate textract_ssml_processor
   ```
3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```
4. **Configure environment variables**
   Create a `.env` file and add your keys (e.g. `OPENAI_API_KEY`).

## Running tests

Currently the project does not include automated tests. Before submitting a pull request, run the application locally to ensure your changes do not break basic functionality:

```bash
flask run
```

You can also run static analysis with [flake8](https://flake8.pycqa.org/) to check for style issues:

```bash
pip install flake8
flake8
```

## Coding standards

- Follow [PEP 8](https://peps.python.org/pep-0008/) for Python code style.
- Keep imports organized and remove unused imports.
- Write docstrings for all public functions and classes.

## Submitting changes

1. Create a new branch for your work.
2. Make your changes and commit with clear messages.
3. Push the branch to your fork and open a pull request.
4. Describe the problem and how your change fixes it.

## Opening issues / PRs

- Use GitHub issues to report bugs or request features. Provide as much context as possible.
- When opening a pull request, link the relevant issue if one exists and ensure the PR description summarizes your changes clearly.

We appreciate all contributions!

# Looplink Starter Project
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

Django project using front-end libraries:

- [HTMX](https://htmx.org/)
- [Alpine](https://alpinejs.dev/)
- [Tailwind CSS](https://tailwindcss.com/)

---

## Where to Look First

If you're new to this project, here are some good starting points:

- **Complete the Dev Environment Setup**
  - The instructions are in the following section.
  - Once complete, you can run `python manage.py runserver` and visit [http://localhost:8000](http://localhost:8000)

- **Using Version Control?**
  - TIP: Make sure you `git init` (or equivalent in mercurial, svn, etc.) and make an initial commit before you add your code to make future commits readable.

- **Default view (landing page)**  
  - Python view: `looplink/ui/base/views.py` (the `default` view)  
  - Template: `looplink/ui/base/templates/base/default.html`

- **HTMX example flow**  
  - Python view: `looplink/ui/base/views.py` (the HTMX example view using `DjangoHtmxActionMixin`)  
  - Entry point: `js_entry` named `base/htmx_example`  
  - Templates:
    - `looplink/ui/base/templates/base/htmx_example.html`
    - `looplink/ui/base/templates/base/partials/htmx/initial_state.html`
    - `looplink/ui/base/templates/base/partials/htmx/step_two.html`
    - `looplink/ui/base/templates/base/partials/htmx/step_three.html`

- **JavaScript and styles**  
  - JavaScript entry points are referenced via the `js_entry` template tag.  
  - App/module-specific assets live in an `assets` folder (for example, `looplink/ui/base/assets/`).  
  - Global styles live in the `styles` folder at the project root (for example, `styles/looplink.css`), which also includes the Tailwind CSS setup.

---

## Dev Environment Setup

### Prerequisites

#### Invoke

This project uses [Invoke](https://www.pyinvoke.org/) for dev automation. Once step 1 below is complete, you can view the list of
available commands with:

```sh
inv -l
```

New commands and updates can be made in the `tasks.py` file.

#### UV

Python dependency management uses [`uv`](https://docs.astral.sh/uv/).

There are [several ways to install `uv`](https://docs.astral.sh/uv/getting-started/installation/). Use whatever method works best for your platform.

- **Linux**

  Ubuntu:

  ```sh
  sudo snap install astral-uv
  ```

- **Mac**

  First install [Homebrew](https://brew.sh/), then use it to install `uv`:

  ```sh
  brew install uv
  ```


### STEP 1: Install Python dependencies

> Python 3.13 is required.

Create a virtualenv with `uv`:

```sh
uv venv
```

Activate the environment:

```sh
source .venv/bin/activate
```

Install Python dependencies:

```sh
uv sync --compile-bytecode
```


### STEP 2: Run the automated initial environment setup

```sh
inv setup-dev-env
```

### STEP 3: Have JavaScript and CSS (SCSS) automatically rebuild on changes

```sh
inv npm -w
```

> NOTE: Restart this command if you add a new `js_entry` path.


### STEP 4: Run the development server

```sh
./manage.py runserver
```


### STEP 5: View in browser

With everything running, visit:

```text
http://localhost:8000/
```

in your browser.

---

## Local Development Notes

Make sure you are using the correct virtual environment (see Dev Environment Setup):

```sh
source .venv/bin/activate
```

To bring up the Docker containers:

```sh
inv docker up
```

To bring down the Docker containers:

```sh
inv docker down
```

To rebuild Docker containers:

```sh
inv docker rebuild
```

To update requirements:

```sh
inv requirements
```

To run the development server (from the terminal):

```sh
python manage.py runserver
```


## Running Tests

To run tests:

```sh
pytest
```

To test a specific app/module:

```sh
pytest looplink/ui/dashboard/tests/test_something.py
```


## Recommended: Linting

We recommend the following linters. Configs are already provided.

- Python: [Ruff](https://github.com/astral-sh/ruff)
- JavaScript: [ESLint](https://eslint.org/)


## HTML Formatting

High-level:

- Two-space indentation
- Attribute line breaks

See [this HTML Guide](https://www.commcarehq.org/styleguide/b5/html/) for full details.


## CSS Formatting

- Two-space indentation


## Dependencies / Requirements

To add a new dependency, run:

```sh
uv add --dev PACKAGE_NAME
```

Alternatively, manually add it to `pyproject.toml`. After a manual edit, run:

```sh
uv lock
```

Update requirements with:

```sh
inv requirements
```

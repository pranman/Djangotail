<!-- markdownlint-disable MD013 MD033 MD041 -->
<div align="center">
<h1>
Django + Tailwind CSS + daisyUI Starter Template
</h1>
</div>

<p align="center">
<a href="https://www.djangoproject.com/"><img src="https://img.shields.io/badge/Django-092E20?style=flat-square&logo=django&logoColor=white" alt="Django badge" /></a>
<a href="https://tailwindcss.com/"><img src="https://img.shields.io/badge/Tailwind_CSS-38B2AC?style=flat-square&logo=tailwind-css&logoColor=white" alt="Tailwind CSS badge" /></a>
<a href="https://daisyui.com/"><img src="https://img.shields.io/badge/daisyUI-5A0EF8?style=flat-square&logo=daisyui&logoColor=white" alt="daisyUI badge" /></a>
<a href="https://python.org/"><img src="https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python badge" /></a>
<a href="https://nodejs.org/"><img src="https://img.shields.io/badge/Node.js-339933?style=flat-square&logo=nodedotjs&logoColor=white" alt="Node.js badge" /></a>
</p>

[Overview](#overview)&nbsp;•
[Features](#features)&nbsp;•
[Installation](#installation)&nbsp;•
[Usage](#usage)&nbsp;•
[Configuration](#configuration)&nbsp;•
[Acknowledgements](#acknowledgements)&nbsp;•
[License](#license)

## Overview <a name="overview"></a>

A Django starter template with Tailwind CSS, daisyUI components, one-command setup, and a tested development workflow.

Use it as a starting point for a Django application with server-rendered templates and a local CSS build.

## Features <a name="features"></a>

- **Django Integration**: Full Django framework with best practices
- **Tailwind CSS**: Utility-first CSS framework for rapid UI development
- **daisyUI Components**: Pre-designed beautiful components built on Tailwind CSS
- **Theme Support**: Multiple themes with easy switching capability
- **Responsive Design**: Mobile-first responsive layouts
- **Environment Configuration**: Environment variables support via dotenv
- **Development Workflow**: Hot-reloading CSS changes during development
- **Production Ready**: Optimised builds for production deployment

## Installation <a name="installation"></a>

1. Clone this repository:
   ```bash
   git clone <your-repository-url>
   cd <project-directory>
   ```

2. Create a virtual environment and activate it:
   ```bash
   python -m venv venv
   # On Windows
   venv\Scripts\activate
   # On macOS/Linux
   source venv/bin/activate
   ```

3. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Create a `.env` file in the project root:
   ```
   # Django Tailwind Configuration
   NPM_BIN_PATH=C:\\Program Files\\nodejs\\npm.cmd
   # For macOS/Linux
   # NPM_BIN_PATH=/usr/bin/npm
   ```

5. Install Tailwind CSS dependencies:
   ```bash
   cd theme
   npm install
   cd ..
   ```

## Usage <a name="usage"></a>

1. Start the Tailwind CSS watcher to compile CSS automatically:
   ```bash
   python manage.py tailwind start
   ```

2. In another terminal, start the Django development server:
   ```bash
   python manage.py runserver
   ```

3. Visit http://localhost:8000 in your browser to see the application.

## Configuration <a name="configuration"></a>

### Tailwind CSS Configuration

The Tailwind CSS configuration is located in `theme/static_src/tailwind.config.js`. You can customise themes, colours, and plugins here.

```javascript
module.exports = {
    // ... other configurations
    plugins: [
        // ... other plugins
        require('daisyui'),
    ],
    daisyui: {
        themes: ["light", "dark", "cupcake"],
    },
}
```

### Django Settings

Key settings for the Django-Tailwind integration:

```python
# settings.py
INSTALLED_APPS = [
    # ... other apps
    'tailwind',
    'theme',
]

TAILWIND_APP_NAME = 'theme'
NPM_BIN_PATH = os.getenv('NPM_BIN_PATH')  # Loaded from .env file
```

### Adding More daisyUI Themes

To add more themes, update the `daisyui.themes` array in `tailwind.config.js`:

```javascript
daisyui: {
    themes: ["light", "dark", "cupcake", "corporate", "synthwave"],
},
```

## Acknowledgements

- [Tom Dekan](https://tomdekan.com/articles/tailwind-with-django) for his helpful article on implementing Tailwind CSS with Django

## License <a name="license"></a>

This project is dual-licensed under both the [MIT License](LICENSE) and the [GNU General Public License v3.0 (GPL-3.0)](LICENSE.GPL).

You may choose either license according to your needs. Please see the corresponding license files for the full terms and conditions. 
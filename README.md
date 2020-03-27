## Installation

Create a virtual environment:

```bash
python -m venv venv
```

Install the requirements

```bash
venv/bin/python -m pip install -r requirements.txt
```

Then install this package:

```bash
venv/bin/python -m pip install -e .
```

## Build the assets

Install node and yarn:

```
# ...
```

Install the node environment:

```
yarn
```

Then build the assets:

```
yarn build
```

## Run the development server

Edit the configuration file (there is an example in `config/template.toml`) then run:

```bash
venv/bin/python -m spotify_party path/to/config.toml
```

Then navigate to http://localhost:5000 or similar.

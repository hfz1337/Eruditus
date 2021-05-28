# Contributions to Eruditus
Thanks for willing to contribute in making Eruditus a better bot!

## How to contribute
You can contribute in different ways, for example, you could:
- Fix a bug
- Fix a typo
- Refactor some code
- Implement a new feature
- Suggest a new feature

## Quick start
1. Fork this repository
2. Clone the forked repository  
`git clone https://github.com/${your_username}/Eruditus`
3. Make a separate branch  
`git checkout -b develop`
4. Make changes locally
5. Stage the affected files  
`git add <files>`
6. Commit your changes  
`git commit -m "short description of your changes"`
7. Push your changes  
`git push origin develop`
8. Make a Pull Request.

## Code style
We're trying to stick to the [PEP 8](https://pep8.org/) standards most of the time, though we don't respect their 79 characters per line recommendation and use 88 instead.  
[PEP 484](https://www.python.org/dev/peps/pep-0484/) type annotations are being used, and for documentation strings (docstrings), we try to use [Google docstrings](https://sphinxcontrib-napoleon.readthedocs.io/en/latest/example_google.html) when possible.  

After writing your code, please consider running [black](https://github.com/psf/black) on it:  
`$ black .`  
As a second pass, consider running [flake8](https://github.com/PyCQA/flake8) using the following command:  
`$ flake8 . --ignore=W503 --max-line-length=88 --show-source`  
Once `flake8` stops reporting warnings, you should be good to go.

Install these tools using: `python3 -m pip install black flake8`

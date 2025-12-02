from setuptools import setup, find_packages

with open("requirements.txt") as f:
	install_requires = f.read().strip().split("\n")

# get version from __version__ variable in egis_integration/__init__.py
from egis_integration import __version__ as version

setup(
	name="egis_integration",
	version=version,
	description="Frappe app for getting data from EGIS using its API",
	author="Phamos",
	author_email="wolfram.schmidt@phamos.eu",
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)

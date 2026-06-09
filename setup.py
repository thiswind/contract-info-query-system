from setuptools import find_packages, setup

setup(
    name="contract-info-query-system",
    version="0.1.0",
    description="Contract information query system",
    package_dir={"": "src"},
    packages=find_packages("src"),
    include_package_data=True,
    package_data={"contract_query": ["templates/*.html", "static/*"]},
    python_requires=">=3.9",
    install_requires=[
        "fastapi",
        "uvicorn[standard]",
        "python-dotenv",
        "openpyxl",
        "jinja2",
        "python-multipart",
        "pypdf",
    ],
    entry_points={
        "console_scripts": [
            "contract-query=contract_query.cli:main",
        ],
    },
)

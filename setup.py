from setuptools import find_packages, setup

setup(
    name="ecosystem",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        'numpy>=1.21.0',
        'pandas>=1.3.0',
        'web3>=5.24.0',
        'scikit-learn>=1.0.0',
        'python-dotenv>=0.19.0',
        'pyyaml>=6.0',
    ],
    python_requires='>=3.8',
)

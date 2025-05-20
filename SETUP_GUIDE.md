# Local Setup Guide

This guide explains how to run Insighter from your local clone of the repository.

## Prerequisites

- Docker Desktop running on your machine
- Python 3.7 or higher
- Node.js

## Steps

1. Open a command prompt in the project directory.
2. Run `install_insighter.bat` to install all dependencies. This will create a
   Python virtual environment, install the Insighter package in editable mode,
   and install Node.js packages.
3. Start the application by running `run_insighter.bat`. This launches Insighter
   using Docker and exposes it on `http://localhost:3000`.

After these steps, you can access Insighter from your browser at
`http://localhost:3000`.

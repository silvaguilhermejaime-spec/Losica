#!/usr/bin/env python3
from losica_engine.working_language import main

if __name__ == "__main__":
    main(["build", *__import__("sys").argv[1:]])

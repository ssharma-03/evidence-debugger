# Stale Code Checks

When a marker is `NOT REACHED`, the code you are editing is **not** the code that is executing. 

**STOP modifying application logic immediately.** If you continue editing logic while markers are unreached, any change you make is either useless or will cause unexpected regressions later.

Follow this checklist to find where the execution path diverges.

---

## 1. Unbuilt Artifacts & Transpilation

If the project uses a compiler, bundler, or transpiler, the runtime executes built output rather than your raw source file:

- **TypeScript / Babel / Webpack / Vite / Rollup**: Are you editing `src/index.ts` while Node executes `dist/index.js` or `build/`? Run the build command (e.g., `npm run build`, `npx tsc`) or check if a watcher is running.
- **Go / Rust / C / C++**: Did you recompile the binary? Ensure the repro command invokes `go test ./...` or `cargo test` rather than an old binary in `./bin` or `/usr/local/bin`.
- **Java / Kotlin / Scala**: Has Gradle or Maven recompiled classfiles (`./gradlew testClasses` or `mvn compile`)?

---

## 2. Python Bytecode, Caches & Shadows

Python can silently run stale bytecode or shadowed modules:

- **`__pycache__` and `.pyc` files**: Stale bytecode can persist if file mtimes are desynchronized. Remove caches:
  `find . -name "*.pyc" -delete -o -name "__pycache__" -delete`
- **Installed vs Local Editable Package**: Is your code installed in `site-packages` or `.venv`?
  Run `python3 -c "import <mod>; print(<mod>.__file__)"`. If it points to `site-packages` instead of your working tree, reinstall in editable mode:
  `pip install -e .`
- **`PYTHONPATH` precedence**: Does `sys.path` place another installation ahead of current working directory? Check `python3 -c "import sys; print(sys.path)"`.

---

## 3. Environment & Process Isolation

- **Virtual Environment vs Global Interpreter**: Check `which python` or `which node`. Is the repro command using the interpreter where your changes are?
- **Containers & Virtual Machines**: Is the repro running inside Docker while you are editing files on the host without a shared volume mount?
- **Background Daemons & Pre-forked Servers**: Does the command communicate with a running background daemon (e.g., Celery worker, Gunicorn, PostgreSQL, Redis) that has not restarted since your edit?

---

## 4. Control Flow & Unreachable Code

If the file is definitely executing, the specific line where the marker was placed might be bypassed:

- **Early Return / Raised Exceptions**: Was an exception raised or return executed *before* reaching your marker line? Move the marker to the top of the function or file entrypoint.
- **Conditional Branching**: Is the marker inside an `if` block whose condition evaluated to `False`? Place a marker right above the condition.
- **Lazy Loading**: Is the module imported lazily inside another function that was never called during this specific test run?

---

## Diagnostic Flow

1. Place marker at the very top of the entrypoint file (line 1).
2. Run `repro`. If top-level marker is reached, the file executes; move the marker downwards to find where execution branches away.
3. If top-level marker is **still not reached**, check interpreter path and build steps using `ed.py envinfo`.

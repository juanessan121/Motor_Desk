import sys
from pathlib import Path

# Entrada explícita para CPython en modo aislado (-I), sin PYTHONPATH.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.local import main

if __name__ == '__main__':
    import sys
    try:
        main()
    except (ValueError, RuntimeError, OSError) as exc:
        print(f'MotorDesk no pudo continuar: {exc}', file=sys.stderr)
        input('Pulse Entrar para cerrar...')
        sys.exit(1)

"""Chargement de la configuration (.env au racine du repo + variables d'env)."""
import os

# Racine du repo (2 niveaux au-dessus de core/ai/)
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _load_dotenv() -> None:
    """Micro-chargeur .env (pas de dépendance supplémentaire).

    Les vraies variables d'environnement prennent toujours le pas.
    """
    candidate = os.path.join(REPO_ROOT, ".env")
    if not os.path.exists(candidate):
        return
    with open(candidate, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()


def env(key: str, default: str | None = None) -> str | None:
    """Lire une variable d'environnement avec valeur par défaut."""
    return os.environ.get(key, default)

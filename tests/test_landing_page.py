from pathlib import Path

import httpx
import pytest

from app.main import app


@pytest.mark.asyncio
async def test_landing_page_renders_editorial_layout_and_safe_entry_points():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/")
    assert response.status_code == 200
    html = response.text
    assert 'class="landing-hero section-shell"' in html
    assert 'hero-console' in html
    assert 'class="pathway-grid"' in html
    assert 'class="trust-rail"' in html
    assert "Construisez en France." in html
    assert html.count('href="/auth/register/"') == 6
    assert html.count('href="/auth/login/"') == 1
    assert 'href="/assistant"' in html
    assert html.count("<h1") == 1


def test_landing_page_is_dense_without_scroll_story_overlays():
    root = Path(__file__).parents[1] / "frontend"
    html = (root / "index.html").read_text(encoding="utf-8")
    css = (root / "styles.css").read_text(encoding="utf-8")
    js = (root / "main.js").read_text(encoding="utf-8")

    assert 'data-story' not in html
    assert 'data-signal=' not in html
    assert 'morphing-story-panel' not in html
    assert "min-height:440vh" not in css
    assert "position:sticky" in css
    assert "prefers-reduced-motion:reduce" in css
    assert "IntersectionObserver" in js
    assert "wheel" not in js
    assert "requestAnimationFrame" not in js


def test_landing_page_has_accessible_menu_and_all_actor_destinations():
    root = Path(__file__).parents[1] / "frontend"
    html = (root / "index.html").read_text(encoding="utf-8")
    css = (root / "styles.css").read_text(encoding="utf-8")
    js = (root / "main.js").read_text(encoding="utf-8")

    assert 'aria-expanded="false"' in html
    assert 'aria-controls="site-nav"' in html
    assert 'id="startup"' in html
    assert 'id="investor"' in html
    assert 'id="researcher"' in html
    assert 'is-open' in js
    assert "[data-reveal].is-visible" in css
    assert "clip-path:inset(100%)" in css


def test_landing_page_preserves_scope_copy_and_navigation():
    html = (Path(__file__).parents[1] / "frontend" / "index.html").read_text(encoding="utf-8")
    watch_copy = "Veille r" + chr(233) + "glementaire en temps r" + chr(233) + "el : perspective post-MVP."
    legal_watch_copy = "Pas de veille juridique en temps r" + chr(233) + "el."
    assert watch_copy in html
    assert legal_watch_copy in html
    assert 'href="#france">Plateforme' in html
    assert 'href="#pathways">Parcours' in html
    assert 'href="#startup">Startups' in html
    assert 'href="#investor">Investisseurs' in html
    assert 'href="#researcher">Recherche' in html
    assert 'href="/docs">Documentation' in html

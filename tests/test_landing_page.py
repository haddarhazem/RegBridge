from pathlib import Path

import httpx
import pytest

from app.main import app


@pytest.mark.asyncio
async def test_landing_page_renders_one_master_story_and_six_scenes():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/")
    assert response.status_code == 200
    html = response.text
    assert 'class="landing-story"' in html
    assert html.count('class="story-viewport"') == 1
    assert html.count('class="morphing-story-panel"') == 1
    assert html.count('data-scene-content=') == 5
    assert 'data-scene="6"' in html
    assert "Construisez en France." in html
    assert "Avec des preuves." in html
    assert html.count('href="/auth/register/"') == 3
    assert html.count('href="/auth/login/"') == 1
    assert 'href="/auth/register/?from=landing"' not in html
    assert 'href="/auth/login/?from=landing"' not in html
    assert 'href="/assistant"' in html
    assert html.count("<h1") == 1


def test_landing_page_has_persistent_states_popups_and_safe_scope_copy():
    root = Path(__file__).parents[1] / "frontend"
    html = (root / "index.html").read_text(encoding="utf-8")
    css = (root / "styles.css").read_text(encoding="utf-8")
    js = (root / "main.js").read_text(encoding="utf-8")
    motion = (root / "motion.js").read_text(encoding="utf-8")

    for state in ("hero", "france", "role", "system", "trust", "cta"):
        assert f'data-panel-layer="{state}"' in html
    for signal in ("france", "startup", "investor", "researcher", "trust"):
        assert f'data-signal="{signal}"' in html
    assert html.count("data-role-headline") == 3
    watch_copy = "Veille r" + chr(233) + "glementaire en temps r" + chr(233) + "el : perspective post-MVP."
    assert watch_copy in html
    legal_watch_copy = "Pas de veille juridique en temps r" + chr(233) + "el."
    assert legal_watch_copy in html

    assert 'font-family:var(--font-sans)' in css
    assert css.count("--font-sans:") == 1
    assert "min-height:440vh" in css
    assert "story-viewport" in css and "morphing-story-panel" in css
    assert "prefers-reduced-motion:reduce" in css
    assert "@media (max-width:600px)" in css
    assert "border-radius:50px" not in css

    assert "MotionProvider" in motion
    assert "requestAnimationFrame" in motion
    assert "passive: true" in motion
    assert "LandingStory" in js and "new MotionProvider" in js
    assert js.count("new MotionProvider") == 1
    assert "wheel" not in js and "wheel" not in motion
    assert "Math.round" not in js and "Math.round" not in motion
    assert "ScrollScene" not in js and "setState" not in js


def test_landing_page_has_keyboard_menu_and_reduced_motion_fallback():
    root = Path(__file__).parents[1] / "frontend"
    html = (root / "index.html").read_text(encoding="utf-8")
    css = (root / "styles.css").read_text(encoding="utf-8")
    js = (root / "main.js").read_text(encoding="utf-8")
    assert 'aria-expanded="false"' in html
    assert 'aria-controls="site-nav"' in html
    assert "is-open" in js
    assert "grid-template-columns:repeat(4,1fr)" in css
    assert "story-content,.panel-layer,.floating-signal" in css


def test_landing_navigation_matrix_uses_stable_fragments_and_informational_roles():
    html = (Path(__file__).parents[1] / "frontend" / "index.html").read_text(encoding="utf-8")

    assert html.count('href="#france">Plateforme') == 2
    assert html.count('href="#pathways" data-pathway-role="startup">Startups') == 2
    assert html.count('href="#pathways" data-pathway-role="investor">Investisseurs') == 2
    assert html.count('href="#pathways" data-pathway-role="researcher">Recherche') == 2
    assert html.count('href="#trust">Confiance') == 2
    assert 'href="#system">Recherche' not in html
    assert html.count('href="/assistant"') == 2
    assert 'href="/docs">Documentation' in html
    assert 'data-pathway-role' in (Path(__file__).parents[1] / "frontend" / "main.js").read_text(encoding="utf-8")

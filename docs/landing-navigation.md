# RegBridge landing navigation matrix

This is the frozen navigation contract for the landing page. Role links only
select an informational pathway; they never authenticate or open a workspace.

| Surface | Label | Destination | Role state |
| --- | --- | --- | --- |
| Header and footer | Plateforme | `#france` | — |
| Header and footer | Startups | `#pathways` | startup |
| Header and footer | Investisseurs | `#pathways` | investor |
| Header and footer | Recherche | `#pathways` | researcher |
| Header and footer | Confiance | `#trust` | — |
| Header | Se connecter | `/auth/login/` | — |
| Header, hero and closing CTA | Commencer | `/auth/register/` | — |
| Hero | Poser une question | `/assistant` | — |
| Closing CTA | Interroger RegBridge | `/assistant` | — |
| Footer | Documentation | `/docs` | — |

The login and registration pages remain visible when a valid session already
exists. They expose an explicit “Continuer vers mon espace” action, which uses
the normal role-aware destination resolver only after the user activates it.

HeroForge-Anew
==============
HeroForge Anew is a character builder spreadsheet for D&D 3.5. It makes the process of character generation far simpler, allowing you to create in minutes what would once have taken hours, and in hours what would once have taken days! Powerful and well designed, it can handle the majority of 3.5 content, and more content is being added. Try it, and never look back!


## WANT TO HELP THIS PROJECT?

I know several of you have offered to help out with this. Well, I finally have something you can do. Now I've put in support for Wild Shape and animal companions, it would be really good if I could get some help with data entry, to add in the stats for more creatures. At the moment, the list of available critters to turn into is pretty limited, and there's barely anything that isn't an animal - so Masters of Many Forms are sad. Anyone up for helping out with that, drop me a message and I'll walk you through the layout and format you need.


## RUNNING THE PYTHON EDITION (QA / ISOLATED RUNTIME)

HeroForge Anew is being rebuilt as a cross-platform Python application (see
[`docs/conversion-plan.md`](docs/conversion-plan.md)). For QA and
user-in-the-loop testing, the app can be spun up in a **separate, isolated
container** and viewed/interacted with from your browser — no host display or
X11 setup required.

```bash
docker compose up --build
# then open http://localhost:6080/vnc.html and click "Connect"
```

This also works in **GitHub Codespaces / VS Code Dev Containers** via the
included `.devcontainer/` configuration. Full instructions are in
[`docs/runtime-environment.md`](docs/runtime-environment.md).

To run the application directly on a desktop machine instead:

```bash
pip install -r requirements.txt
pip install -e .
python -m heroforge
```


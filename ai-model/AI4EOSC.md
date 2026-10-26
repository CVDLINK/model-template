# Offering a model on the AI4EOSC Marketplace

**Never use real patient data with a model on this platform.** Try-me sessions and platform
deployments run on infrastructure outside CVDLINK, and anything a user uploads is processed
there. Only synthetic or public example inputs belong on it.

CVDLINK publishes models through GitHub and Zenodo, which makes them citable and findable in
OpenAIRE and EOSC. The AI4EOSC Marketplace adds something different: a copy of the model that
other people can **run**, as a public container image or a short browser session. It is
optional, and it only suits a model that can be fully open.

## Before you start: is your model a fit?

All of these must hold:

- The code **and the weights** can be public under an open licence.
- The model is called once per input (predict and, optionally, train). A multi-site federated
  workflow does not fit.
- Someone will keep the listing working after the project ends: the platform's schema, base images
  and build pipeline keep changing.

## What becomes public, and who can run it

- **The source repository** is public and lives in the platform's GitHub organisation
  `ai4os-hub`. The platform team creates it, gives you access, and reviews your code before the
  module is listed.
- **The container image** is public on Docker Hub (`ai4oshub/<name>`) and in the platform
  registry. Anyone can pull and run it without an account.
- **Try-me**: a 10-minute browser session for anyone with an institutional (eduGAIN) login.
- **Deploying or retraining on platform GPUs** needs full platform access, given to members of the
  platform's partner projects or on request to their support.
- **A second Zenodo record.** The platform's build switches on the Zenodo integration for the
  module repository, so its releases are archived there too, with their own DOI. Keep the CVDLINK
  record as the one you cite, and link the two records to each other.

## 1 · Create the module from the template

Work outside this repository: the module is a separate project with its own repository.

```bash
pip install cookiecutter
cookiecutter https://github.com/ai4os/ai4-template
cd <module-name>      # the folder cookiecutter just created; run every later command here
```

Use [`ai4-template-adv`](https://github.com/ai4os/ai4-template-adv) instead if your model code
should stay in its own repository and be pulled in as a dependency. Its files are laid out
differently, so for steps 2 and 3 follow its own README; steps 4 to 6 are the same.

At the licence prompt pick **MIT**, **BSD-3-Clause** or **AGPL-3.0-only**. Two choices are broken
in the template today: "Apache 2.0" does not install until you change `pyproject.toml` to
`license = "Apache-2.0"`, and "No license file" does not install at all.

## 2 · Fix two template defects before the first push

A freshly generated module fails the platform's own checks, and a module that fails them never
gets an image built:

- In `<package>/config.py`, replace `"license": PACKAGE_METADATA["License"]` with
  `"license": PACKAGE_METADATA.get("License-Expression") or PACKAGE_METADATA.get("License")`.
  Newer setuptools stores the licence in the first field, so without this the API reports
  `"license": null` and the template's own test fails.
- In `tests/test_api.py`, the author string in `test_model_metadata_values` is indented one space
  short and fails flake8 (E131). Add the space.

## 3 · Wrap your model

In `<package>/api.py`, fill in `get_predict_args()` and `predict()` (and `get_train_args()` and
`train()` if the model can be retrained). Keep `get_metadata()` as the template wrote it. Then
check it locally:

```bash
pip install -e .
deepaas-run --listen-ip 127.0.0.1
# metadata:  GET  http://127.0.0.1:5000/v2/models/
# predict:   POST http://127.0.0.1:5000/v2/models/<package>/predict/
```

## 4 · Fill in and validate the metadata

`ai4-metadata.yml` ships with `tags`, `tasks`, `categories` and `libraries` commented out, but all
four are required. Uncomment them, choose values from the allowed lists, and validate the way the
platform's build does:

```bash
pip install ai4-metadata
ai4-metadata validate --metadata-version 2.0.0 ai4-metadata.yml
```

## 5 · Run the platform's checks locally

```bash
pip install tox
tox -e qc.sty,qc.cov,qc.sec      # flake8, tests with coverage, bandit
```

The documentation's `tox -e .` does not work with current tox.

## 6 · Ask for the listing

- [ ] Open an issue in [ai4os-hub/modules-catalog](https://github.com/ai4os-hub/modules-catalog/issues/new)
      with the module name, a one-line summary and your GitHub username. There is no issue
      template. The catalogue maintainer has said e-mail can be quicker; the support address is
      below.
- [ ] Push your code to the repository the platform team creates for you. The `Dockerfile` builds
      from that GitHub repository, not from your local files, so a local `docker build` only
      works after this push. The default base image is old (TensorFlow 2.9.1); choose a current
      one in the Dockerfile.
- [ ] After review the module is added to the catalogue. The documentation says it appears about
      six hours later. The one earlier request in the tracker took about two weeks from issue to
      listing.
- [ ] Add the marketplace link to your CVDLINK repository's `README.md`, next to the DOI.

## Contacts

- Module requests: the [modules-catalog issue tracker](https://github.com/ai4os-hub/modules-catalog/issues)
- Platform helpdesk: <https://helpdesk.cloud.ai4eosc.eu/>
- Support e-mail: ai4eosc-support@listas.csic.es

Checked against the platform on 16 October 2026 with a dry run of the template; the platform
changes often, so re-check a step that fails.

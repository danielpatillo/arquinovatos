# Distribution and Manager registration

GitHub is the distribution target for this node pack. Hugging Face hosts the separately licensed GGUF model artifacts referenced by the Downloader.

The distribution repository is `https://github.com/danielpatillo/arquinovatos`.

## Current publication status

The repository is public and was verified empty before publishing this reviewed release. The pack can be cloned or downloaded through GitHub. Public Manager search remains pending catalogue acceptance; the registration proposal is being submitted from the author's fork of ComfyUI-Manager.

The source ZIP can already be installed manually by placing its `Arquinovatos_Prompt_Enhancer` folder inside `ComfyUI/custom_nodes` and restarting ComfyUI.

## Public Manager search

There are two documented registration paths:

1. **Comfy Registry:** register a publisher, add its real `PublisherId` to `pyproject.toml`, create a publishing API key and use `comfy node publish`. The publishing package version is `0.0.2`; the user-facing version is `v0.0.02`. No key belongs in this repository. [Official publishing guide](https://docs.comfy.org/registry/publishing).
2. **Manager catalogue proposal:** after the GitHub repository is public, submit an entry to `Comfy-Org/ComfyUI-Manager/custom-node-list.json`. Inclusion depends on maintainers merging the proposal and Manager updating its catalogue/cache. [Official Manager registration instructions](https://github.com/Comfy-Org/ComfyUI-Manager#how-to-register-your-custom-node-into-comfyui-manager).

The pack's three public class names are declared explicitly and described in `node_list.json`. That file is a name-to-description object matching Manager's scanner.

A downloadable repository, an open catalogue proposal, an approved Registry version and an actual Manager search result are separate states. This release is validated locally; no Registry version has been published and no public Manager search inclusion is claimed.

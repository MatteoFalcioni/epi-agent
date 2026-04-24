# epi-agent
Agentic AI system with epidemiologic simulations & data-analysis capabilities 

## Quick Start 

### 1. Clone & Install

*Recommended: create a `conda` environment or a python `venv` first, for complete isolation*

Then:

```bash
git clone https://github.com/MatteoFalcioni/epi-agent
cd epi-agent
pip install -r requirements.txt
```

### 2. Download `Ollama` and pull a model

This system runs on local llm's downloaded in your machine, through [`Ollama`](https://ollama.com/). 

To use it, first download `Ollama`; run:

- Linux: `curl -fsSL https://ollama.com/install.sh | sh`
- Mac: `curl -fsSL https://ollama.com/install.sh | sh`
- Windows: `irm https://ollama.com/install.ps1 | iex`

Then to download a model to your machine: 

```sh
ollama pull qwen3.5:0.8b
```

You will see something like

```zsh
pulling manifest 
pulling afb707b6b8fa: 100% ▕██████████████████████████████████████████████████████████▏ 1.0 GB                         
pulling 9be69ef46306: 100% ▕██████████████████████████████████████████████████████████▏  11 KB                         
pulling 9371364b27a5: 100% ▕██████████████████████████████████████████████████████████▏   65 B                         
pulling b14c6eab49f9: 100% ▕██████████████████████████████████████████████████████████▏  476 B                         
verifying sha256 digest 
writing manifest 
success 
```

You can then run it from shell like this:

```zsh
ollama run qwen3.5:0.8b
```

and you can use it in LangChain like this: 

```python
llm = ChatOllama(
    model="qwen3.5:0.8b"
)
```

Find all models [here](https://ollama.com/search).

#### Important Note

You must be aware that bigger models are heavier to run. 

For a first estimate of models you can run depending on your GPU - because **you need a GPU** - you can use this website: https://apxml.com/tools/vram-calculator

Notice that some models may "fit" in VRAM but will be slower than other for inference. For example, Deepseek is usually slower locally then Qwen. So you should experiment with different models in your size range.

### 3. Configure Environment [Optional]

If you want to implement tracing in LangSmith (to check the agent's trajectory and reasoning) you need to 

Set up LangSmith [here](https://smith.langchain.com/o/2b3dff8d-ea0b-44a3-a981-4377843f21c8). Learn more about Langsmith traces [here](https://docs.langchain.com/langsmith/create-account-api-key#create-an-account-and-api-key).

Then create `.env` from template:

```bash
cp .env.template .env
```

And put the trace variables from LangSmith in `env`

```
LANGSMITH_TRACING=<your key>
LANGSMITH_ENDPOINT=<your key>
LANGSMITH_API_KEY=<your key>
LANGSMITH_PROJECT=<your project>
```

### 4. Run the agent

```bash

python src/main.py

```


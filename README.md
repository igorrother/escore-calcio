# Escore de Cálcio de Agatston

Aplicativo desktop (Windows e macOS) para pontuação manual de cálcio coronariano
pelo método de Agatston a partir de tomografia computadorizada cardíaca não
contrastada em DICOM.

> ⚠️ **Apenas para pesquisa e ensino.** Não é um dispositivo médico, não foi
> aprovado por nenhum órgão regulador, e **NÃO** deve ser usado para diagnóstico
> clínico, tratamento, rastreamento ou decisões de manejo de pacientes.

---

## Baixar

Acesse a [página de Releases](https://github.com/igorrother/escore-calcio/releases)
e baixe o arquivo correspondente ao seu sistema:

| Sistema operacional | Arquivo |
|---|---|
| **Windows 10/11** | `EscoreCalcio-v<X.Y>.zip` |
| **macOS** (Apple Silicon — M1, M2, M3, M4) | `EscoreCalcio-v<X.Y>-mac-arm64.zip` |

Sempre prefira a versão mais recente no topo da página.

---

## Executar no Windows

1. Extraia o `.zip` em qualquer pasta (Área de Trabalho, Documentos, etc.).
2. Dentro da pasta extraída `EscoreCalcio/`, dê **duplo clique** em
   `EscoreCalcio.exe`.
3. Na **primeira execução**, o Windows pode exibir uma tela azul com a
   mensagem **"O Windows protegeu seu PC"** ("Windows protected your PC"):
   - Clique em **Mais informações**
   - Em seguida, clique em **Executar assim mesmo**

   Isso só acontece uma vez. O aviso aparece porque o aplicativo ainda
   não está assinado digitalmente — não há malware, é apenas uma proteção
   do Windows contra publicadores desconhecidos.

> ⚠️ **Não mova** `EscoreCalcio.exe` para fora da pasta. Ele precisa da subpasta
> `_internal/` que fica ao lado dele para funcionar.

---

## Executar no macOS

1. Extraia o `.zip` (duplo clique já basta).
2. Arraste `EscoreCalcio.app` para a pasta **Aplicativos** (ou execute direto
   de onde estiver).
3. Na **primeira execução**, o macOS pode bloquear o app com a mensagem
   **"EscoreCalcio.app não pode ser aberto porque a Apple não pode verificar
   se ele contém malware"**:
   - **Botão direito** (ou Ctrl + clique) em `EscoreCalcio.app` → **Abrir**
   - Confirme **Abrir** no diálogo

   Só precisa fazer isso uma vez. A partir daí, basta duplo clique normal.
   Mesmo motivo do Windows — o app ainda não está notarizado pela Apple.

> Requer macOS 11 Big Sur ou mais recente, em Mac com chip Apple Silicon.

---

## Como usar

1. **Abrir um estudo** — vá em **Arquivo → Abrir Pasta…** ou
   **Arquivo → Abrir ZIP…**, ou simplesmente **arraste uma pasta ou ZIP
   DICOM** para qualquer parte da janela.
2. **Escolher a série** — o seletor mostra todas as séries de TC encontradas;
   séries candidatas a escore de cálcio (3 mm, descrição típica) são
   destacadas em verde no topo.
3. **Marcar as calcificações** — pixels ≥ 130 HU aparecem em **rosa**
   ("marcação candidata"). Na barra de ferramentas:
   - **Artéria** — escolha a coronária que está marcando: **TCE, DA, Cx, CD, DP**
     (botões coloridos, cada artéria com sua cor)
   - **Ferramenta** — *Preenchimento* (clique uma calcificação) ou
     *Mão livre* (clique e arraste em volta de uma área)
   - **Borracha** — clique em uma ROI marcada para removê-la
   - **Olho com íris colorida** — oculta/mostra todos os overlays
   - **Olho com íris rosa** — oculta/mostra apenas a marcação candidata rosa
4. **Reatribuir artéria** — basta clicar em uma ROI já marcada com **outra
   artéria selecionada** na barra; a cor da ROI muda e o escore é
   redistribuído entre as artérias.
5. **Painel à direita** atualiza ao vivo:
   - Cabeçalho do paciente (nome, ID, sexo, idade, data do estudo)
   - Subtotal por artéria
   - Escore total de Agatston + classificação de risco
   - Percentil MESA (aparece quando o escore total > 0)

### Atalhos úteis

| Ação | Atalho |
|---|---|
| Próxima/anterior fatia | scroll do mouse, ↑/↓, PageUp/PageDown |
| Ajustar contraste (W/L) | arrastar com **botão direito** |
| Cancelar polígono em desenho | **Esc** |
| Abrir pasta | Ctrl + O |
| Abrir ZIP | Ctrl + Shift + O |
| Sair | Ctrl + Q |

---

## Regras de pontuação (Agatston)

- Pixel só conta se **HU ≥ 130**
- Lesão precisa ter área **≥ 1 mm²** para pontuar (filtra ruído de imagem)
- Fator de densidade pelo HU **máximo** da lesão:

  | HU máximo | Peso |
  |---|---|
  | 130–199 | ×1 |
  | 200–299 | ×2 |
  | 300–399 | ×3 |
  | ≥ 400 | ×4 |

- Escore da lesão = área (mm²) × peso
- Escore total = soma de todas as lesões de todas as fatias

### Classificação de risco (6 níveis, pt-BR)

| Escore total | Classificação |
|---|---|
| 0 | ausente |
| > 0 e < 10 | mínimo |
| 10 – 99 | discreto |
| 100 – 399 | moderado |
| 400 – 999 | acentuado |
| ≥ 1000 | muito acentuado |

### Percentil MESA

O percentil é estimado a partir dos dados de referência do estudo MESA
(McClelland *et al.*, Circulation 2006), estratificados por:

- **Idade** (interpolado entre 45 e 84 anos; idades fora dessa faixa são
  arredondadas para o endpoint mais próximo)
- **Sexo** (lido do cabeçalho DICOM)
- **Raça/Etnia** (selecionável: Branca, Preta, Hispânica, Chinesa)

Faixas exibidas: `<25`, `25–50`, `50–75`, `75–90`, `>90`.

---

## Para desenvolvedores

Requer Python 3.11+. O CI (`.github/workflows/release.yml`) compila
automaticamente para Windows + macOS Apple Silicon a cada tag `v*` empurrada.

### Setup local

```bash
git clone https://github.com/igorrother/escore-calcio
cd escore-calcio
python -m venv .venv

# Windows
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe main.py

# macOS / Linux
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py
```

### Testes

```bash
python -m pytest
```

### Build local (Windows)

```
build_windows.bat        # produz dist\EscoreCalcio\EscoreCalcio.exe
package_zip.bat          # produz dist\EscoreCalcio-vX.Y.zip
```

(Os `.bat` ficam em `.gitignore` — releases reais saem do CI.)

### Lançar uma nova versão

1. Atualize `__version__` em `calcium_score/__init__.py`
2. Commit + tag + push:
   ```bash
   git commit -am "chore: bump version to 1.1"
   git tag v1.1
   git push origin main --tags
   ```
3. O workflow `Build & release` no GitHub Actions compila ambos os sistemas
   e publica uma Release com os zips anexados em alguns minutos.

---

## Crédito

Desenvolvido por **Igor Rother Cesar de Oliveira**.

Não associado, financiado ou endossado por nenhum hospital, universidade
ou empresa.

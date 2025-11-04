(function() {
  if (window.__irisPlusWidgetLoaded) return;
  window.__irisPlusWidgetLoaded = true;

  const panel = document.createElement('div');
  panel.innerHTML = `
    <style>
      #irisplus-panel {
        position: fixed;
        bottom: 20px;
        right: 20px;
        background: #2a2b2e;
        color: #e8eaed;
        font-family: 'Segoe UI', Arial, sans-serif;
        border-radius: 14px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.4);
        padding: 16px;
        width: 280px;
        z-index: 999999;
      }
      #irisplus-panel label {
        font-size: 0.85rem;
        color: #cfcfcf;
      }
      #irisplus-panel input, #irisplus-panel select {
        width: 100%;
        background: #3a3b3e;
        color: #fff;
        border: none;
        border-radius: 8px;
        margin-top: 5px;
        margin-bottom: 10px;
        padding: 4px;
      }
      #irisplus-panel button {
        background: #8ab4f8;
        color: #202124;
        font-weight: bold;
        padding: 8px 16px;
        border: none;
        border-radius: 10px;
        cursor: pointer;
        width: 100%;
      }
      #irisplus-panel button:hover {
        background: #5f97f6;
      }
      #irisplus-panel .status {
        text-align: center;
        margin-top: 10px;
        font-weight: bold;
      }
    </style>
    <div id="irisplus-panel">
      <h4 style="margin:0 0 10px 0; text-align:center;">🌀 Iris+</h4>
      <label>Amplitude (px):</label>
      <input type="range" id="irisplus-amp" min="1" max="20" value="5">
      <label>Freq. direita (mov/s):</label>
      <input type="range" id="irisplus-freq-dir" min="1" max="20" value="5">
      <label>Freq. esquerda (mov/s):</label>
      <input type="range" id="irisplus-freq-esq" min="1" max="20" value="5">
      <label>Direção:</label>
      <select id="irisplus-dir">
        <option value="horizontal">Horizontal</option>
        <option value="vertical">Vertical</option>
        <option value="ambos">Ambos</option>
      </select>
      <button id="irisplus-toggle">Ativar Simulação</button>
      <div class="status" id="irisplus-status">🔴 Inativo</div>
    </div>
  `;
  document.body.appendChild(panel);

  let ativo = false;
  let intervalo;
  let deslocamento = 0;

  function aplicarTremor(amplitude, freqDir, freqEsq, direcao) {
    const alvo = document.body;
    let tempo = 0;
    if (intervalo) clearInterval(intervalo);

    intervalo = setInterval(() => {
      // Assimetria: lado positivo usa freqDir, lado negativo usa freqEsq
      let fase;
      if (Math.sin(tempo) >= 0) {
        fase = Math.sin(tempo * freqDir / freqEsq);
      } else {
        fase = Math.sin(tempo * freqEsq / freqDir);
      }

      deslocamento = amplitude * fase;
      tempo += (Math.PI * 2) / 60;

      if (direcao === 'horizontal') {
        alvo.style.transform = `translateX(${deslocamento}px)`;
      } else if (direcao === 'vertical') {
        alvo.style.transform = `translateY(${deslocamento}px)`;
      } else {
        alvo.style.transform = `translate(${deslocamento}px, ${fase * amplitude}px)`;
      }
    }, 16);
  }

  document.getElementById('irisplus-toggle').addEventListener('click', () => {
    const amp = parseInt(document.getElementById('irisplus-amp').value);
    const freqDir = parseInt(document.getElementById('irisplus-freq-dir').value);
    const freqEsq = parseInt(document.getElementById('irisplus-freq-esq').value);
    const dir = document.getElementById('irisplus-dir').value;
    const status = document.getElementById('irisplus-status');
    const btn = document.getElementById('irisplus-toggle');

    if (!ativo) {
      ativo = true;
      aplicarTremor(amp, freqDir, freqEsq, dir);
      status.textContent = '🟢 Ativo';
      btn.textContent = 'Desativar Simulação';
    } else {
      ativo = false;
      clearInterval(intervalo);
      document.body.style.transform = '';
      status.textContent = '🔴 Inativo';
      btn.textContent = 'Ativar Simulação';
    }
  });
})();
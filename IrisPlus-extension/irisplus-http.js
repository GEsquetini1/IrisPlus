(function() {
  if (window.__irisPlusHttpLoaded) return;
  window.__irisPlusHttpLoaded = true;

  // Configurações do servidor HTTP
  const SERVER_URL = 'http://localhost:8765';
  let isConnected = false;
  let pollingInterval = null;
  let lastData = null;

  // Criar painel flutuante (mesmo HTML anterior, mas com lógica HTTP)
  const panel = document.createElement('div');
  panel.innerHTML = `
    <style>
      /* Mesmo CSS anterior*/
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
        width: 320px;
        z-index: 999999;
        border: 2px solid #333;
      }
      #irisplus-panel h4 {
        margin: 0 0 12px 0;
        text-align: center;
        color: #8ab4f8;
      }
      #irisplus-panel .status {
        text-align: center;
        margin: 10px 0;
        font-weight: bold;
        padding: 8px;
        border-radius: 8px;
      }
      #irisplus-panel .connected {
        background: #0a3a0a;
        color: #4ade80;
      }
      #irisplus-panel .disconnected {
        background: #3a0a0a;
        color: #f87171;
      }
      #irisplus-panel .data-display {
        background: #1a1b1e;
        padding: 10px;
        border-radius: 8px;
        margin: 8px 0;
        font-size: 0.8rem;
      }
      #irisplus-panel .data-row {
        display: flex;
        justify-content: space-between;
        margin: 4px 0;
      }
      #irisplus-panel button {
        background: #8ab4f8;
        color: #202124;
        font-weight: bold;
        padding: 10px 16px;
        border: none;
        border-radius: 10px;
        cursor: pointer;
        width: 100%;
        margin: 5px 0;
      }
      #irisplus-panel button:hover {
        background: #5f97f6;
      }
      #irisplus-panel button:disabled {
        background: #666;
        cursor: not-allowed;
      }
      #irisplus-panel .controls {
        margin-top: 12px;
      }
      #irisplus-panel label {
        display: block;
        margin: 8px 0 4px 0;
        font-size: 0.85rem;
        color: #cfcfcf;
      }
      #irisplus-panel input[type="range"] {
        width: 100%;
        margin: 5px 0;
      }
    </style>
    <div id="irisplus-panel">
      <h4>🌀 Iris+ HTTP</h4>
      
      <div class="status disconnected" id="irisplus-status">
        🔴 DESCONECTADO
      </div>
      
      <div class="data-display" id="irisplus-data">
        <div class="data-row">
          <span>Íris Esquerda:</span>
          <span id="left-iris">-</span>
        </div>
        <div class="data-row">
          <span>Íris Direita:</span>
          <span id="right-iris">-</span>
        </div>
        <div class="data-row">
          <span>Distância:</span>
          <span id="distance">-</span>
        </div>
        <div class="data-row">
          <span>Frame:</span>
          <span id="frame">-</span>
        </div>
      </div>
      
      <div class="controls">
        <label>Sensibilidade Movimento:</label>
        <input type="range" id="irisplus-sensitivity" min="0.1" max="2.0" step="0.1" value="1.0">
        
        <label>Compensação Ativa:</label>
        <select id="irisplus-compensation">
          <option value="none">Nenhuma</option>
          <option value="horizontal">Horizontal</option>
          <option value="vertical">Vertical</option>
          <option value="both" selected>Ambas</option>
        </select>
        
        <button id="irisplus-connect">Conectar Servidor</button>
        <button id="irisplus-toggle" disabled>Ativar Compensação</button>
      </div>
    </div>
  `;
  document.body.appendChild(panel);

  // Elementos do DOM
  const statusElement = document.getElementById('irisplus-status');
  const connectButton = document.getElementById('irisplus-connect');
  const toggleButton = document.getElementById('irisplus-toggle');
  const sensitivitySlider = document.getElementById('irisplus-sensitivity');
  const compensationSelect = document.getElementById('irisplus-compensation');

  // Estado da aplicação
  let compensationActive = false;
  let sensitivity = 1.0;
  let lastLeftIris = { x: 0, y: 0 };
  let lastRightIris = { x: 0, y: 0 };

  // Polling para buscar dados
  function startPolling() {
    pollingInterval = setInterval(async () => {
      try {
        const response = await fetch(`${SERVER_URL}/data`);
        if (response.ok) {
          const data = await response.json();
          if (data.status !== 'no_data') {
            lastData = data;
            updateDisplay(data);
            
            if (compensationActive) {
              applyCompensation(data);
            }
          }
        }
      } catch (error) {
        // Silencioso - erro de conexão é normal se servidor não estiver rodando
      }
    }, 50); // 20 FPS
  }

  function stopPolling() {
    if (pollingInterval) {
      clearInterval(pollingInterval);
      pollingInterval = null;
    }
  }

  // Conectar/Desconectar
  function connectServer() {
    if (!isConnected) {
      isConnected = true;
      statusElement.textContent = '🟢 CONECTADO';
      statusElement.className = 'status connected';
      connectButton.textContent = 'Desconectar';
      toggleButton.disabled = false;
      startPolling();
    } else {
      isConnected = false;
      statusElement.textContent = '🔴 DESCONECTADO';
      statusElement.className = 'status disconnected';
      connectButton.textContent = 'Conectar Servidor';
      toggleButton.disabled = true;
      toggleButton.textContent = 'Ativar Compensação';
      compensationActive = false;
      stopPolling();
    }
  }

  // Resto das funções permanecem iguais...
  function updateDisplay(data) {
    document.getElementById('left-iris').textContent = 
      `${data.left_iris.x}, ${data.left_iris.y}`;
    document.getElementById('right-iris').textContent = 
      `${data.right_iris.x}, ${data.right_iris.y}`;
    document.getElementById('distance').textContent = 
      `${data.distance_cm ? data.distance_cm.toFixed(1) : 0} cm`;
    document.getElementById('frame').textContent = data.frame_number;
  }

  function applyCompensation(data) {
    const contentElements = document.querySelectorAll('p, h1, h2, h3, h4, h5, h6, span, div:not(#irisplus-panel):not(#irisplus-panel *)');
    
    const avgX = (data.left_iris.x + data.right_iris.x) / 2;
    const avgY = (data.left_iris.y + data.right_iris.y) / 2;
    
    const deltaX = avgX - ((lastLeftIris.x + lastRightIris.x) / 2);
    const deltaY = avgY - ((lastLeftIris.y + lastRightIris.y) / 2);
    
    lastLeftIris = { ...data.left_iris };
    lastRightIris = { ...data.right_iris };
    
    const compensationType = compensationSelect.value;
    let transformX = 0;
    let transformY = 0;
    
    if (compensationType === 'horizontal' || compensationType === 'both') {
      transformX = -deltaX * sensitivity * 0.1;
    }
    
    if (compensationType === 'vertical' || compensationType === 'both') {
      transformY = -deltaY * sensitivity * 0.1;
    }
    
    contentElements.forEach(element => {
      element.style.transform = `translate(${transformX}px, ${transformY}px)`;
      element.style.transition = 'transform 0.1s ease-out';
    });
  }

  // Event Listeners
  connectButton.addEventListener('click', connectServer);

  toggleButton.addEventListener('click', function() {
    compensationActive = !compensationActive;
    
    if (compensationActive) {
      toggleButton.textContent = 'Desativar Compensação';
      if (lastData) {
        lastLeftIris = { ...lastData.left_iris };
        lastRightIris = { ...lastData.right_iris };
      }
    } else {
      toggleButton.textContent = 'Ativar Compensação';
      document.querySelectorAll('p, h1, h2, h3, h4, h5, h6, span, div').forEach(element => {
        element.style.transform = '';
      });
    }
  });

  sensitivitySlider.addEventListener('input', function() {
    sensitivity = parseFloat(this.value);
  });

  // Conectar automaticamente após 1 segundo
  setTimeout(() => {
    connectServer();
  }, 1000);

})();
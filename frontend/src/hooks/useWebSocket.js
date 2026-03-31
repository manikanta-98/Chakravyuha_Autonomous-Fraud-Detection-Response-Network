import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import useWebSocket from 'react-use-websocket';

const WebSocketContext = createContext();

export const useWebSocketContext = () => {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error('useWebSocketContext must be used within a WebSocketProvider');
  }
  return context;
};

export const WebSocketProvider = ({ children }) => {
  const [socketUrl] = useState(`ws://localhost:8000/ws/transactions`);
  const [transactionUpdates, setTransactionUpdates] = useState([]);
  const [agentStatus, setAgentStatus] = useState({});
  const [isConnected, setIsConnected] = useState(false);

  const { sendMessage, lastMessage, readyState } = useWebSocket(socketUrl, {
    onOpen: () => {
      console.log('WebSocket connected');
      setIsConnected(true);
    },
    onClose: () => {
      console.log('WebSocket disconnected');
      setIsConnected(false);
    },
    onError: (error) => {
      console.error('WebSocket error:', error);
      setIsConnected(false);
    },
    shouldReconnect: (closeEvent) => true,
    reconnectAttempts: 10,
    reconnectInterval: 3000,
  });

  useEffect(() => {
    if (lastMessage !== null) {
      try {
        const data = JSON.parse(lastMessage.data);

        if (data.type === 'updates') {
          data.updates.forEach(update => {
            if (update.stream === 'transactions:risk') {
              setTransactionUpdates(prev => [update.data, ...prev.slice(0, 49)]); // Keep last 50
            } else if (update.stream === 'agent_health') {
              setAgentStatus(update.data);
            }
          });
        }
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
      }
    }
  }, [lastMessage]);

  const sendTransaction = useCallback((transaction) => {
    if (readyState === 1) { // OPEN
      sendMessage(JSON.stringify({
        type: 'transaction',
        data: transaction
      }));
    }
  }, [sendMessage, readyState]);

  const value = {
    transactionUpdates,
    agentStatus,
    isConnected,
    sendTransaction,
    readyState
  };

  return (
    <WebSocketContext.Provider value={value}>
      {children}
    </WebSocketContext.Provider>
  );
};

"""
mlp_numpy.py
MLP (Perceptrón Multicapa) seguro, modular, solo NumPy, sin dependencias externas.
Cumple reglas de seguridad y compatibilidad incremental.
"""

import numpy as np
import logging

logging.basicConfig(level=logging.INFO)

class MLP:
    """
    MLP simple, thread-safe para inferencia, sin dependencias externas salvo numpy.
    """
    def __init__(self, input_size, hidden_sizes, output_size, seed=None):
        if seed is not None:
            np.random.seed(seed)
        self.sizes = [input_size] + hidden_sizes + [output_size]
        self.weights = [np.random.randn(self.sizes[i], self.sizes[i+1]) * np.sqrt(2/self.sizes[i])
                        for i in range(len(self.sizes)-1)]
        self.biases = [np.zeros((1, s)) for s in self.sizes[1:]]

    def _relu(self, x):
        return np.maximum(0, x)

    def _relu_deriv(self, x):
        return (x > 0).astype(float)

    def _softmax(self, x):
        e_x = np.exp(x - np.max(x, axis=1, keepdims=True))
        return e_x / np.sum(e_x, axis=1, keepdims=True)

    def forward(self, X):
        a = X
        activations = [a]
        zs = []
        for w, b in zip(self.weights[:-1], self.biases[:-1]):
            z = np.dot(a, w) + b
            zs.append(z)
            a = self._relu(z)
            activations.append(a)
        z = np.dot(a, self.weights[-1]) + self.biases[-1]
        zs.append(z)
        a = self._softmax(z)
        activations.append(a)
        return activations, zs

    def backward(self, X, y, activations, zs):
        grads_w = [np.zeros_like(w) for w in self.weights]
        grads_b = [np.zeros_like(b) for b in self.biases]
        m = X.shape[0]
        y_onehot = np.zeros_like(activations[-1])
        y_onehot[np.arange(m), y] = 1
        delta = activations[-1] - y_onehot
        grads_w[-1] = np.dot(activations[-2].T, delta) / m
        grads_b[-1] = np.sum(delta, axis=0, keepdims=True) / m
        for l in range(2, len(self.sizes)):
            z = zs[-l]
            delta = np.dot(delta, self.weights[-l+1].T) * self._relu_deriv(z)
            grads_w[-l] = np.dot(activations[-l-1].T, delta) / m
            grads_b[-l] = np.sum(delta, axis=0, keepdims=True) / m
        return grads_w, grads_b

    def update(self, grads_w, grads_b, lr):
        for i in range(len(self.weights)):
            self.weights[i] -= lr * grads_w[i]
            self.biases[i] -= lr * grads_b[i]

    def fit(self, X, y, epochs=100, lr=0.01, verbose=False):
        for epoch in range(epochs):
            activations, zs = self.forward(X)
            grads_w, grads_b = self.backward(X, y, activations, zs)
            self.update(grads_w, grads_b, lr)
            if verbose and (epoch % 10 == 0 or epoch == epochs-1):
                loss = -np.mean(np.log(activations[-1][np.arange(len(y)), y] + 1e-8))
                logging.info(f"Epoch {epoch+1}/{epochs} - Loss: {loss:.4f}")

    def predict(self, X):
        activations, _ = self.forward(X)
        return np.argmax(activations[-1], axis=1)

    def predict_proba(self, X):
        activations, _ = self.forward(X)
        return activations[-1]

# Ejemplo seguro de uso (no se ejecuta al importar)
if __name__ == "__main__":
    # XOR demo
    X = np.array([[0,0],[0,1],[1,0],[1,1]])
    y = np.array([0,1,1,0])
    mlp = MLP(input_size=2, hidden_sizes=[8,8], output_size=2, seed=42)
    mlp.fit(X, y, epochs=200, lr=0.1, verbose=True)
    preds = mlp.predict(X)
    print("Predicciones:", preds)

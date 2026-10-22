"""
code_auditor.py
Auditor de código seguro: analiza scripts Python usando AST, calcula complejidad ciclomática y detecta malas prácticas.
No ejecuta código, cumple reglas de seguridad y compatibilidad.
"""
import ast
import logging
from typing import List, Dict, Any

logging.basicConfig(level=logging.INFO)

class CodeAuditor:
    def __init__(self):
        pass

    def analyze_file(self, file_path: str) -> Dict[str, Any]:
        """
        Analiza un archivo Python: AST, complejidad, malas prácticas.
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                code = f.read()
            tree = ast.parse(code, filename=file_path)
        except Exception as e:
            logging.error(f"Error al analizar {file_path}: {e}")
            return {"error": str(e)}
        return {
            "file": file_path,
            "complexity": self.cyclomatic_complexity(tree),
            "bad_practices": self.detect_bad_practices(tree),
            "functions": self.list_functions(tree)
        }

    def cyclomatic_complexity(self, tree: ast.AST) -> int:
        """
        Calcula la complejidad ciclomática total del archivo.
        """
        class ComplexityVisitor(ast.NodeVisitor):
            def __init__(self):
                self.complexity = 0
            def generic_visit(self, node):
                if isinstance(node, (ast.If, ast.For, ast.While, ast.And, ast.Or, ast.ExceptHandler, ast.With, ast.Try, ast.BoolOp, ast.FunctionDef, ast.AsyncFunctionDef)):
                    self.complexity += 1
                ast.NodeVisitor.generic_visit(self, node)
        visitor = ComplexityVisitor()
        visitor.visit(tree)
        return visitor.complexity + 1  # +1 por el flujo base

    def detect_bad_practices(self, tree: ast.AST) -> List[str]:
        """
        Detecta malas prácticas básicas (uso de eval, exec, import *, etc).
        """
        issues = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in ("eval", "exec"):
                    issues.append(f"Uso inseguro de {node.func.id} en línea {node.lineno}")
            if isinstance(node, ast.ImportFrom) and node.module and node.names:
                if any(alias.name == '*' for alias in node.names):
                    issues.append(f"Importación insegura 'from {node.module} import *' en línea {node.lineno}")
        return issues

    def list_functions(self, tree: ast.AST) -> List[str]:
        """
        Lista nombres de funciones definidas en el archivo.
        """
        return [n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]

# Ejemplo seguro de uso
if __name__ == "__main__":
    auditor = CodeAuditor()
    resultado = auditor.analyze_file("mlp_numpy.py")
    print("Reporte de auditoría:", resultado)

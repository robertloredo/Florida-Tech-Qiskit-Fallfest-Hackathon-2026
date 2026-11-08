"""Fall Fest environment check."""
import sys

print(f"Python: {sys.version.split()[0]}")

import qiskit
print(f"Qiskit: {qiskit.__version__}")

try:
    import qiskit_ibm_runtime
    print(f"Runtime client: {qiskit_ibm_runtime.__version__}")
except ImportError:
    print("Runtime client: NOT INSTALLED")

from qiskit import QuantumCircuit
from qiskit.primitives import StatevectorSampler

qc = QuantumCircuit(2)
qc.h(0)
qc.cx(0, 1)
qc.measure_all()

result = StatevectorSampler().run([qc], shots=1000).result()
counts = result[0].data.meas.get_counts()

print("\nBell State Simulator Test:")
print(f"Measurement counts: {counts}")
print("Setup check completed.")
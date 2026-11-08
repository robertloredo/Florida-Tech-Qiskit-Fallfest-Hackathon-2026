from qiskit_ibm_runtime import QiskitRuntimeService

service = QiskitRuntimeService()

for backend in service.backends():
    status = backend.status()

    print(f"\nBackend: {backend.name}")
    print("Qubits:", backend.num_qubits)
    print("Operational:", status.operational)
    print("Pending jobs:", status.pending_jobs)
    print("Simulator:", backend.simulator)
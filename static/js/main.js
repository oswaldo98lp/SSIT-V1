/**
 * Admón Almacén SSIT 2.0 - Client Javascript Engine
 * Integrates HTMX, Bootstrap 5 Modals, Toasts and Global UX helpers.
 */

document.addEventListener("DOMContentLoaded", () => {
  // Inicializar Toasts de Bootstrap 5
  const toastElList = [].slice.call(document.querySelectorAll('.toast'));
  toastElList.map((toastEl) => {
    const toast = new bootstrap.Toast(toastEl, { delay: 4000 });
    toast.show();
    return toast;
  });

  // Manejador global para modales HTMX
  const modalElement = document.getElementById("main-modal");
  if (modalElement) {
    const bsModal = new bootstrap.Modal(modalElement);

    document.body.addEventListener("htmx:afterSwap", (e) => {
      // Si el swap ocurrió en el target del modal, abrirlo automáticamente
      if (e.detail.target.id === "modal-dialog-content") {
        bsModal.show();
      }
    });

    document.body.addEventListener("closeModal", () => {
      bsModal.hide();
    });
  }
});

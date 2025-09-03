// Modal utility functions for better UX
class ModalManager {
  constructor() {
    this.activeModal = null;
    this.createModalContainer();
  }

  createModalContainer() {
    // Create modal container if it doesn't exist
    if (!document.getElementById('modal-container')) {
      const container = document.createElement('div');
      container.id = 'modal-container';
      container.className = 'fixed inset-0 z-50 hidden';
      document.body.appendChild(container);
    }
  }

  showModal(config) {
    const container = document.getElementById('modal-container');
    
    const modal = document.createElement('div');
    modal.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4';
    modal.onclick = (e) => {
      if (e.target === modal && config.allowBackdropClose !== false) {
        this.closeModal();
      }
    };

    const dialog = document.createElement('div');
    dialog.className = 'bg-white rounded-lg shadow-xl max-w-md w-full mx-4';
    
    // Header
    if (config.title) {
      const header = document.createElement('div');
      header.className = 'flex items-center justify-between p-6 pb-3';
      
      const title = document.createElement('h3');
      title.className = 'text-lg font-semibold text-gray-900';
      title.textContent = config.title;
      
      const closeBtn = document.createElement('button');
      closeBtn.className = 'text-gray-400 hover:text-gray-600 focus:outline-none';
      closeBtn.innerHTML = '×';
      closeBtn.style.fontSize = '24px';
      closeBtn.onclick = () => this.closeModal();
      
      header.appendChild(title);
      header.appendChild(closeBtn);
      dialog.appendChild(header);
    }

    // Body
    const body = document.createElement('div');
    body.className = 'px-6 py-3';
    
    if (config.message) {
      const message = document.createElement('p');
      message.className = 'text-gray-600 mb-4';
      message.textContent = config.message;
      body.appendChild(message);
    }

    if (config.input) {
      const inputGroup = document.createElement('div');
      inputGroup.className = 'mb-4';
      
      if (config.input.label) {
        const label = document.createElement('label');
        label.className = 'block text-sm font-medium text-gray-700 mb-2';
        label.textContent = config.input.label;
        inputGroup.appendChild(label);
      }
      
      const input = document.createElement('input');
      input.type = config.input.type || 'text';
      input.className = 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent';
      input.placeholder = config.input.placeholder || '';
      input.value = config.input.value || '';
      input.id = 'modal-input';
      
      // Auto-focus and select all text
      setTimeout(() => {
        input.focus();
        input.select();
      }, 100);
      
      // Handle Enter key
      input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          const confirmBtn = dialog.querySelector('[data-action="confirm"]');
          if (confirmBtn) confirmBtn.click();
        } else if (e.key === 'Escape') {
          this.closeModal();
        }
      });
      
      inputGroup.appendChild(input);
      body.appendChild(inputGroup);
      
      // Validation message area
      const validationMsg = document.createElement('div');
      validationMsg.id = 'validation-message';
      validationMsg.className = 'text-sm text-red-600 hidden mt-1';
      inputGroup.appendChild(validationMsg);
    }

    dialog.appendChild(body);

    // Footer
    const footer = document.createElement('div');
    footer.className = 'flex justify-end gap-3 px-6 py-4 bg-gray-50 rounded-b-lg';
    
    // Cancel button
    const cancelBtn = document.createElement('button');
    cancelBtn.className = 'px-4 py-2 text-gray-600 hover:text-gray-800 focus:outline-none';
    cancelBtn.textContent = config.cancelText || 'Cancel';
    cancelBtn.onclick = () => {
      this.closeModal();
      if (config.onCancel) config.onCancel();
    };
    footer.appendChild(cancelBtn);
    
    // Confirm button
    const confirmBtn = document.createElement('button');
    confirmBtn.className = 'px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500';
    confirmBtn.textContent = config.confirmText || 'OK';
    confirmBtn.setAttribute('data-action', 'confirm');
    confirmBtn.onclick = () => {
      if (config.input) {
        const inputValue = document.getElementById('modal-input').value;
        
        // Validation
        if (config.input.validate && !config.input.validate(inputValue)) {
          const validationMsg = document.getElementById('validation-message');
          validationMsg.textContent = config.input.validationMessage || 'Invalid input';
          validationMsg.classList.remove('hidden');
          return;
        }
        
        this.closeModal();
        if (config.onConfirm) config.onConfirm(inputValue);
      } else {
        this.closeModal();
        if (config.onConfirm) config.onConfirm();
      }
    };
    footer.appendChild(confirmBtn);
    
    dialog.appendChild(footer);
    modal.appendChild(dialog);
    container.appendChild(modal);
    
    // Show modal
    container.classList.remove('hidden');
    this.activeModal = modal;
    
    // Prevent body scroll
    document.body.style.overflow = 'hidden';
  }

  closeModal() {
    const container = document.getElementById('modal-container');
    if (container && this.activeModal) {
      container.classList.add('hidden');
      container.innerHTML = '';
      this.activeModal = null;
      document.body.style.overflow = '';
    }
  }

  // Utility methods for common modal types
  confirm(title, message, onConfirm, onCancel) {
    this.showModal({
      title,
      message,
      confirmText: 'Confirm',
      cancelText: 'Cancel',
      onConfirm,
      onCancel
    });
  }

  prompt(title, message, defaultValue = '', onConfirm, onCancel, options = {}) {
    this.showModal({
      title,
      message,
      input: {
        label: options.label,
        placeholder: options.placeholder,
        value: defaultValue,
        type: options.type || 'text',
        validate: options.validate,
        validationMessage: options.validationMessage
      },
      confirmText: options.confirmText || 'Save',
      cancelText: 'Cancel',
      onConfirm,
      onCancel
    });
  }

  alert(title, message, onConfirm) {
    this.showModal({
      title,
      message,
      confirmText: 'OK',
      onConfirm,
      allowBackdropClose: false
    });
  }
}

// Global modal manager instance
window.modalManager = new ModalManager();

// Toast notification system
class ToastManager {
  constructor() {
    this.createToastContainer();
  }

  createToastContainer() {
    if (!document.getElementById('toast-container')) {
      const container = document.createElement('div');
      container.id = 'toast-container';
      container.className = 'fixed top-4 right-4 z-50 space-y-2';
      document.body.appendChild(container);
    }
  }

  show(message, type = 'info', duration = 5000) {
    const container = document.getElementById('toast-container');
    
    const toast = document.createElement('div');
    toast.className = `px-4 py-3 rounded-md shadow-lg transform transition-all duration-300 translate-x-full opacity-0`;
    
    // Set colors based on type
    const typeClasses = {
      success: 'bg-green-500 text-white',
      error: 'bg-red-500 text-white',
      warning: 'bg-yellow-500 text-white',
      info: 'bg-blue-500 text-white'
    };
    
    toast.className += ` ${typeClasses[type] || typeClasses.info}`;
    
    // Toast content
    const content = document.createElement('div');
    content.className = 'flex items-center justify-between gap-3';
    
    const messageEl = document.createElement('span');
    messageEl.textContent = message;
    content.appendChild(messageEl);
    
    // Close button
    const closeBtn = document.createElement('button');
    closeBtn.className = 'text-white hover:text-gray-200 focus:outline-none';
    closeBtn.innerHTML = '×';
    closeBtn.style.fontSize = '18px';
    closeBtn.onclick = () => this.remove(toast);
    content.appendChild(closeBtn);
    
    toast.appendChild(content);
    container.appendChild(toast);
    
    // Animate in
    setTimeout(() => {
      toast.classList.remove('translate-x-full', 'opacity-0');
    }, 100);
    
    // Auto remove
    if (duration > 0) {
      setTimeout(() => {
        this.remove(toast);
      }, duration);
    }
    
    return toast;
  }

  remove(toast) {
    toast.classList.add('translate-x-full', 'opacity-0');
    setTimeout(() => {
      if (toast.parentNode) {
        toast.parentNode.removeChild(toast);
      }
    }, 300);
  }

  success(message, duration) {
    return this.show(message, 'success', duration);
  }

  error(message, duration) {
    return this.show(message, 'error', duration);
  }

  warning(message, duration) {
    return this.show(message, 'warning', duration);
  }

  info(message, duration) {
    return this.show(message, 'info', duration);
  }
}

// Global toast manager instance
window.toastManager = new ToastManager();

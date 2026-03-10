// Toggle the visibility of the dialog by calling the ui('#dialog') function from BeerCSS when receiving the closeDialog event
// Used when closing the dialog needs to be handled after form validation. The trigger is sent by HX-Trigger in the header of the response
document.body.addEventListener('closeDialog', function(evt) {
    ui('#dialog');
});

// Dismiss flash messages on click
document.body.addEventListener('click', function(evt) {
    const flashMessage = evt.target.closest('.flash-message');
    
    // If a flash message was clicked and it's not already being dismissed
    if (flashMessage && !flashMessage.classList.contains('dismiss')) {
        // Add the class to trigger the fade-out animation
        flashMessage.classList.add('dismiss');
        
        // Remove the element from the DOM after the animation finishes
        flashMessage.addEventListener('animationend', () => {
            flashMessage.remove();
        }, { once: true }); // The listener will automatically remove itself after firing once
    }
});

// Enable/disable share input when an LCE member toggle is switched
function toggleShare(checkbox, inputId) {
    const input = document.getElementById(inputId);
    if (checkbox.checked) {
        input.disabled = false;
        input.required = true;
        input.focus();
    } else {
        input.disabled = true;
        input.required = false;
        input.value = '';
        const field = input.closest('.field');
        if (field) {
            field.classList.remove('invalid');
            field.querySelector('span.error')?.remove();
        }
    }
}

// Hold button functionality
const holdDuration = 2000;
let holdTimer = null;

function startHold(button) {
    // Add visual feedback
    button.style.setProperty('--hold-duration', holdDuration + 'ms');
    button.classList.add('error');
    
    // Clear any existing timer
    if (holdTimer) {
        clearTimeout(holdTimer);
    }
    
    // Set timer for 5 seconds
    holdTimer = setTimeout(() => {
        // Trigger custom event that htmx is listening for
        button.dispatchEvent(new CustomEvent('hold-complete'));
        // Reset visual state
        button.classList.remove('error');
        holdTimer = null;
    }, holdDuration);
}

function cancelHold(button) {
    // Clear the timer if button is released
    if (holdTimer) {
        clearTimeout(holdTimer);
        holdTimer = null;
    }
    // Remove visual feedback
    button.style.setProperty('--hold-duration', '200ms');
    button.classList.remove('error');
}

// Map BeerCSS classes for invalid inputs with HTML5 validation
document.addEventListener('invalid', (function () {
    return function (e) {
      // Prevent the browser's default validation pop-up
      e.preventDefault();
  
      // Find the parent .field element
      const field = e.target.closest('.field');
      if (field) {
        // Add the 'invalid' class to the parent
        field.classList.add('invalid');
  
        // Find or create the error message span
        let error = field.querySelector('span.error');
        if (!error) {
          error = document.createElement('span');
          error.className = 'error';
          // Insert after the input or the last element in .field
          field.appendChild(error);
        }
        // Set the error message from the validation API
        error.textContent = e.target.validationMessage;
      }
    };
  })(), true);
  
  // Listener to remove validation errors when the user corrects them
  document.addEventListener('input', function (e) {
    const field = e.target.closest('.field');
    // Check if the input is inside a .field that is marked as invalid
    if (field && field.classList.contains('invalid')) {
      // Check the validity of the input
      if (e.target.checkValidity()) {
        // If it's valid, remove the 'invalid' class
        field.classList.remove('invalid');
        // And remove the error message span
        const error = field.querySelector('span.error');
        if (error) {
          error.remove();
        }
      }
    }
  });

  // Dark theme toggle
  const themeToggleIcons = '#theme-toggle > i';

  function setThemeIcon(mode) {
      const icon = mode === 'dark' ? 'light_mode' : 'dark_mode';
      document.querySelectorAll(themeToggleIcons).forEach(el => {
          if (el) el.textContent = icon;
      });
  }
  
  function toggleTheme() {
      const newMode = ui('mode') === 'dark' ? 'light' : 'dark';
      ui('mode', newMode);
      setThemeIcon(newMode);
      localStorage.setItem('theme', newMode);
  }
  
  document.addEventListener('DOMContentLoaded', () => {
      // Check for saved theme preference
      const savedTheme = localStorage.getItem('theme');
      if (savedTheme && savedTheme !== ui('mode')) {
          ui('mode', savedTheme);
      }
      setThemeIcon(ui('mode'));
  });
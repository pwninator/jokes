
  const firebaseConfig = {"apiKey": "test", "authDomain": "example.firebaseapp.com", "projectId": "example"};
  const nextUrl = "/admin";
  const errorEl = document.getElementById('login-error');
  const button = document.getElementById('google-signin');

  if (button) {
    function showError(message) {
      if (!errorEl) return;
      errorEl.textContent = message;
      errorEl.style.display = 'block';
    }

    button.addEventListener('click', async () => {
      if (errorEl) {
        errorEl.style.display = 'none';
      }
      button.disabled = true;
      try {
        const app = await import('https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js');
        const authModule = await import('https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js');

        const initializedApp = app.getApps().length
          ? app.getApp()
          : app.initializeApp(firebaseConfig);
        const auth = authModule.getAuth(initializedApp);
        auth.languageCode = 'en';

        const provider = new authModule.GoogleAuthProvider();
        provider.setCustomParameters({ prompt: 'select_account' });

        const result = await authModule.signInWithPopup(auth, provider);
        const idToken = await result.user.getIdToken(true);

        const response = await fetch('/admin/session', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
          credentials: 'same-origin',
          body: JSON.stringify({ idToken }),
        });

        if (!response.ok) {
          throw new Error('Unable to create session. Please ensure your account has admin access.');
        }

        try {
          await authModule.signOut(auth);
        } catch (signOutErr) {
          console.warn('Failed to sign out Firebase Auth session', signOutErr); // eslint-disable-line no-console
        }

        window.location.href = nextUrl || '/admin';
      } catch (err) {
        console.error('Admin login failed', err); // eslint-disable-line no-console
        showError(err?.message ?? 'Sign-in failed. Please try again.');
      } finally {
        button.disabled = false;
      }
    });
  } else {
    console.error('Google sign-in button missing'); // eslint-disable-line no-console
  }

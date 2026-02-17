# Connect this project to GitHub

Your repo is already set to use SSH: `git@github.com:AdenCap/landscape-saas.git`.  
You need an SSH key on your Mac and added to your GitHub account.

---

## Option A: Generate a new SSH key (recommended)

**1. Create a key** (in Terminal):

```bash
ssh-keygen -t ed25519 -C "your_email@example.com" -f ~/.ssh/id_ed25519_github -N ""
```

Use your real email. You can leave the passphrase empty (`-N ""`) for passwordless push, or type one for extra security.

**2. Start the ssh-agent and add the key:**

```bash
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519_github
```

**3. Add the key to GitHub:**

- Copy your **public** key to the clipboard:

  ```bash
  pbcopy < ~/.ssh/id_ed25519_github.pub
  ```

- In the browser: **GitHub → Settings → SSH and GPG keys → New SSH key**
- Title: e.g. `MacBook`
- Key: paste (Cmd+V) and save

**4. Tell SSH to use this key for GitHub:**

Create or edit `~/.ssh/config`:

```
Host github.com
  HostName github.com
  User git
  IdentityFile ~/.ssh/id_ed25519_github
```

**5. Test:**

```bash
ssh -T git@github.com
```

You should see: `Hi AdenCap! You've successfully authenticated...`

**6. Push:**

```bash
cd "/Users/adencappelletti/Desktop/Landscape Software/landscape-saas"
git push origin main
```

---

## Option B: Use HTTPS instead of SSH

If you prefer username + Personal Access Token:

**1. Switch remote to HTTPS:**

```bash
cd "/Users/adencappelletti/Desktop/Landscape Software/landscape-saas"
git remote set-url origin https://github.com/AdenCap/landscape-saas.git
```

**2. Create a token:**  
GitHub → Settings → Developer settings → Personal access tokens → **Tokens (classic)** → Generate new token.  
Give it **repo** scope, copy the token.

**3. Push (Git will ask for username and password):**

```bash
git push origin main
```

- Username: `AdenCap`
- Password: paste your **token** (not your GitHub password)

---

## Quick test after connecting

```bash
cd "/Users/adencappelletti/Desktop/Landscape Software/landscape-saas"
git push origin main
```

If that works, you’re connected.

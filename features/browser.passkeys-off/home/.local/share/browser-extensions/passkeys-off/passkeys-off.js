// Passkeys Off: runs in every frame before the page's own scripts (MAIN world, document_start).
//
// Sites decide whether to push "create a passkey" and whether to offer passkey autofill from
// PublicKeyCredential's capability checks, so those report nothing available. Creating a passkey
// is refused. The background (conditional) request behind passkey autofill never completes, as if
// the user never picked one, so a page that retries on failure does not loop. A modal
// navigator.credentials.get() still goes through: it is a sign-in the page asked for explicitly,
// such as a security-key second factor, and refusing it could lock an account out.
(() => {
  "use strict";
  const PublicKey = globalThis.PublicKeyCredential;
  const Container = globalThis.CredentialsContainer;
  if (typeof PublicKey !== "function" || typeof Container !== "function") return;

  const replace = (target, name, fn) => {
    if (typeof target[name] !== "function") return;
    Object.defineProperty(target, name, { value: fn, writable: true, configurable: true, enumerable: false });
  };
  const refused = () =>
    Promise.reject(new DOMException("Passkeys are turned off in this browser (Passkeys Off).", "NotAllowedError"));
  const untilAborted = (signal) =>
    new Promise((_, reject) => {
      if (!signal) return;
      if (signal.aborted) reject(signal.reason);
      else signal.addEventListener("abort", () => reject(signal.reason), { once: true });
    });

  replace(PublicKey, "isUserVerifyingPlatformAuthenticatorAvailable", function isUserVerifyingPlatformAuthenticatorAvailable() {
    return Promise.resolve(false);
  });
  replace(PublicKey, "isConditionalMediationAvailable", function isConditionalMediationAvailable() {
    return Promise.resolve(false);
  });
  const getClientCapabilities = PublicKey.getClientCapabilities;
  replace(PublicKey, "getClientCapabilities", async function getClientCapabilities_() {
    const reported = await getClientCapabilities.call(PublicKey);
    return Object.fromEntries(Object.keys(reported).map((capability) => [capability, false]));
  });

  const originalCreate = Container.prototype.create;
  const originalGet = Container.prototype.get;
  replace(Container.prototype, "create", function create(options) {
    if (options && options.publicKey) return refused();
    return originalCreate.apply(this, arguments);
  });
  replace(Container.prototype, "get", function get(options) {
    if (options && options.publicKey && options.mediation === "conditional") return untilAborted(options.signal);
    return originalGet.apply(this, arguments);
  });
})();

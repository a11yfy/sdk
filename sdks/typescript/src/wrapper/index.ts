// Hand-written overlay — NOT generated. Protected by .fernignore.
//
// This is the PACKAGE ENTRY (see package.json "exports"). It mirrors the
// generated src/index.ts but ships the extended client (with remediate())
// instead of the bare generated one, and adds the webhook helpers.

export * as A11yfy from "../api/index.js";
export type { BaseClientOptions, BaseRequestOptions } from "../BaseClient.js";
export { A11yfyEnvironment } from "../environments.js";
export { A11yfyError, A11yfyTimeoutError } from "../errors/index.js";
export * from "../exports.js";

export {
    A11yfyClient,
    JobFailedError,
    RemediationTimeoutError,
    DEFAULT_POLL_INTERVAL_MS,
    DEFAULT_TIMEOUT_MS,
    DEFAULT_CERTIFICATE_WAIT_MS,
    type FileInput,
    type RemediateOptions,
} from "./A11yfyClient.js";
export {
    Webhooks,
    WebhookVerificationError,
    DEFAULT_TOLERANCE_SECONDS,
    type WebhookEvent,
} from "./webhooks.js";

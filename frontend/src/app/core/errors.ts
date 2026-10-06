import { HttpErrorResponse } from '@angular/common/http';

/** Turns FastAPI / network errors into a short message for the user. */
export function errorMessage(error: unknown): string {
  if (error instanceof HttpErrorResponse) {
    const detail = (error.error as { detail?: unknown } | null)?.detail;
    if (typeof detail === 'string') {
      return detail;
    }
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0] as { msg?: string };
      return first.msg ?? 'The request was not valid.';
    }
    return error.status === 0 ? 'Could not reach the local backend.' : `Request failed (${error.status}).`;
  }
  return error instanceof Error ? error.message : 'Something went wrong.';
}

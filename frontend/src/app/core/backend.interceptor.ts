import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { from, switchMap } from 'rxjs';
import { BackendService } from './backend.service';

/** Sends relative API paths (e.g. `/settings`) to the local backend with the per-launch token. */
export const backendInterceptor: HttpInterceptorFn = (req, next) => {
  if (!req.url.startsWith('/')) {
    return next(req);
  }
  const backend = inject(BackendService);
  return from(backend.resolve()).pipe(
    switchMap((info) =>
      next(
        req.clone({
          url: info.baseUrl + req.url,
          headers: info.token ? req.headers.set('X-App-Token', info.token) : req.headers,
        }),
      ),
    ),
  );
};

import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideRouter, withHashLocation } from '@angular/router';
import { backendInterceptor } from './core/backend.interceptor';
import { routes } from './app.routes';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    // Hash routing: the packaged app is served from a custom protocol with no server-side rewrites.
    provideRouter(routes, withHashLocation()),
    provideHttpClient(withInterceptors([backendInterceptor])),
  ],
};

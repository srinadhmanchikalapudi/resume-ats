import { Routes } from '@angular/router';
import { SettingsPage } from './features/settings/settings';

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'settings' },
  { path: 'settings', component: SettingsPage },
  { path: '**', redirectTo: 'settings' },
];

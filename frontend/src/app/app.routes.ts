import { Routes } from '@angular/router';
import { JobsPage } from './features/jobs/jobs';
import { ProfilePage } from './features/profile/profile';
import { SettingsPage } from './features/settings/settings';

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'profile' },
  { path: 'profile', component: ProfilePage },
  { path: 'jobs', component: JobsPage },
  { path: 'settings', component: SettingsPage },
  { path: '**', redirectTo: 'profile' },
];

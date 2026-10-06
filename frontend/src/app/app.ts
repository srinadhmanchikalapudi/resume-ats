import { Component, OnInit, inject } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { UpdaterService } from './core/updater.service';
import { UpdateBanner } from './update-banner/update-banner';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, RouterLink, RouterLinkActive, UpdateBanner],
  templateUrl: './app.html',
  styleUrl: './app.scss',
})
export class App implements OnInit {
  private readonly updater = inject(UpdaterService);

  ngOnInit(): void {
    // Fire and forget: a failed or offline check must never block the app.
    void this.updater.checkForUpdate();
  }
}

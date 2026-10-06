import { Component, computed, input, model, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ModelInfo } from '../../core/models';
import { filterModels, formatContext, formatPrice } from '../model-filter';

/** Searchable model dropdown that also accepts any custom model ID typed in. */
@Component({
  selector: 'app-model-picker',
  imports: [FormsModule],
  templateUrl: './model-picker.html',
  styleUrl: './model-picker.scss',
})
export class ModelPicker {
  readonly label = input.required<string>();
  readonly hint = input('');
  readonly placeholder = input('e.g. anthropic/claude-sonnet-5-5');
  readonly models = input<ModelInfo[]>([]);
  readonly value = model('');

  protected readonly open = signal(false);
  protected readonly matches = computed(() => filterModels(this.models(), this.value()));

  protected readonly formatPrice = formatPrice;
  protected readonly formatContext = formatContext;

  protected select(choice: ModelInfo): void {
    this.value.set(choice.id);
    this.open.set(false);
  }

  protected close(): void {
    // Delay so a click on a list item registers before the list disappears.
    setTimeout(() => this.open.set(false), 120);
  }
}

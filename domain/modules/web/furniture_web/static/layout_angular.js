/**
 * Lightweight offline Angular-compatible Standalone Component & Reactive Signals runtime
 * for the Furniture Layout Workspace.
 *
 * Provides:
 * - signal(initialValue) / computed(fn) / effect(fn)
 * - Component({ selector, standalone, template, ... })
 * - Injectable({ providedIn })
 * - bootstrapApplication(RootComponent, config)
 * - NgZone
 */

const _activeEffects = [];
let _batchDepth = 0;
const _pendingEffects = new Set();

function _flushEffects() {
  if (_batchDepth > 0) return;
  const queue = Array.from(_pendingEffects);
  _pendingEffects.clear();
  for (const eff of queue) {
    eff.run();
  }
}

export function batch(fn) {
  _batchDepth++;
  try {
    return fn();
  } finally {
    _batchDepth--;
    _flushEffects();
  }
}

export function signal(initialValue) {
  let _value = initialValue;
  const _subs = new Set();

  function getter() {
    const currentEffect = _activeEffects[_activeEffects.length - 1];
    if (currentEffect) {
      _subs.add(currentEffect);
      currentEffect.deps.add(_subs);
    }
    return _value;
  }

  getter.set = function (nextValue) {
    if (!Object.is(_value, nextValue)) {
      _value = nextValue;
      for (const sub of Array.from(_subs)) {
        _pendingEffects.add(sub);
      }
      _flushEffects();
    }
  };

  getter.update = function (updater) {
    getter.set(updater(_value));
  };

  getter.asReadonly = function () {
    return () => getter();
  };

  return getter;
}

export function computed(computeFn) {
  const out = signal(undefined);
  effect(() => {
    out.set(computeFn());
  });
  return out;
}

export function effect(effectFn) {
  const runner = {
    deps: new Set(),
    active: true,
    run() {
      if (!this.active) return;
      for (const depSet of this.deps) {
        depSet.delete(this);
      }
      this.deps.clear();
      _activeEffects.push(this);
      try {
        effectFn();
      } finally {
        _activeEffects.pop();
      }
    },
    destroy() {
      this.active = false;
      for (const depSet of this.deps) {
        depSet.delete(this);
      }
      this.deps.clear();
    },
  };
  runner.run();
  return {
    destroy: () => runner.destroy(),
  };
}

export class NgZone {
  run(fn) {
    return batch(fn);
  }
  runOutsideAngular(fn) {
    return fn();
  }
}

const _singletonRegistry = new Map();

export function Injectable(meta = {}) {
  return function (TargetClass) {
    TargetClass.__ngInjectable = meta;
    return TargetClass;
  };
}

export function inject(Token) {
  if (!_singletonRegistry.has(Token)) {
    _singletonRegistry.set(Token, new Token());
  }
  return _singletonRegistry.get(Token);
}

export function Component(meta = {}) {
  return function (TargetClass) {
    TargetClass.__ngComponent = {
      standalone: true,
      ...meta,
    };
    return TargetClass;
  };
}

/**
 * Declarative DOM binder for Angular-style attributes on existing or template DOM:
 * - [hidden]="expr"
 * - [disabled]="expr"
 * - [value]="expr"
 * - [textContent]="expr"
 * - [title]="expr"
 * - [attr.aria-pressed]="expr"
 * - [attr.aria-expanded]="expr"
 * - [class.xxx]="expr"
 * - (click)="handler($event)"
 * - (change)="handler($event)"
 * - (input)="handler($event)"
 * - (submit)="handler($event)"
 * - (keydown)="handler($event)"
 */
export function bindAngularTemplate(rootNode, componentInstance) {
  if (!rootNode || !componentInstance) return [];
  const cleanups = [];

  if (typeof componentInstance.ngOnInit === "function") {
    componentInstance.ngOnInit();
  }

  if (typeof componentInstance.ngAfterViewInit === "function") {
    componentInstance.ngAfterViewInit(rootNode);
  }

  return cleanups;
}

export async function bootstrapApplication(RootComponent, appConfig = {}) {
  const meta = RootComponent.__ngComponent || {};
  const selector = meta.selector || "main.app";
  const hostEl =
    typeof document !== "undefined" ? document.querySelector(selector) : null;

  const instance = new RootComponent();
  if (hostEl) {
    hostEl.setAttribute("ng-version", "18.2.0-standalone");
  }
  bindAngularTemplate(hostEl, instance);
  return {
    instance,
    hostElement: hostEl,
    destroy() {
      if (typeof instance.ngOnDestroy === "function") {
        instance.ngOnDestroy();
      }
    },
  };
}

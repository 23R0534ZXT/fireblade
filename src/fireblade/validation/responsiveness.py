"""QA-only attribution of UI stalls, without recording data or query arguments."""
import os
import sys
import threading
import time
import traceback


class ResponsivenessProbe:
    def __init__(self):
        self.main_thread = threading.get_ident()
        self.stop_event = threading.Event()
        self.latest_stack = []
        self.sampling_gaps = []
        self.native_calls = []
        self.call_stack = []
        self.previous_profile = sys.getprofile()
        self.started = time.monotonic()
        self.thread = threading.Thread(target=self.sample, daemon=True, name='Fireblade QA sampler')
        self.thread.start()
        sys.setprofile(self.profile)

    def sample(self):
        last = time.monotonic()
        previous = []
        while not self.stop_event.wait(.025):
            now = time.monotonic()
            frame = sys._current_frames().get(self.main_thread)
            stack = [dict(file=os.path.basename(f.filename), line=f.lineno, function=f.name)
                     for f in traceback.extract_stack(frame, limit=12)] if frame else []
            if now-last > .25:
                self.sampling_gaps.append(dict(seconds=round(now-last,4), before=previous, after=stack))
                self.sampling_gaps = sorted(self.sampling_gaps,key=lambda item:item['seconds'],reverse=True)[:20]
            self.latest_stack = stack
            previous, last = stack, now

    def profile(self, frame, event, argument):
        if event not in ('c_call','c_return','c_exception'):
            return
        module = getattr(argument,'__module__','') or ''
        owner = getattr(argument,'__self__',None)
        if 'duckdb' not in module and 'duckdb' not in type(owner).__module__:
            return
        name = getattr(argument,'__name__',type(argument).__name__)
        if event == 'c_call':
            self.call_stack.append((name,time.monotonic(),os.path.basename(frame.f_code.co_filename),frame.f_lineno))
        elif self.call_stack:
            called,started,filename,line = self.call_stack.pop()
            elapsed = time.monotonic()-started
            if elapsed > .1:
                self.native_calls.append(dict(function=called,seconds=round(elapsed,4),file=filename,line=line))
                self.native_calls = sorted(self.native_calls,key=lambda item:item['seconds'],reverse=True)[:30]

    def stop(self):
        sys.setprofile(self.previous_profile)
        self.stop_event.set()
        self.thread.join(.5)
        return dict(main_thread_native_calls=self.native_calls,sampler_gaps=self.sampling_gaps,
                    interpretation='Sampler gaps can reflect GIL contention or host scheduling; native call timings identify work executed synchronously by the UI thread.')

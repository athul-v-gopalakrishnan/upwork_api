class JobCounter:
    def __init__(self):
        self.session_jobs_count = 0

    def increment(self):
        self.session_jobs_count += 1

    def get_count(self):
        return self.session_jobs_count
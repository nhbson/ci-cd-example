from rq.job import Job

def enqueue_links(self, links, task):
    self.log(f"📤 Sending {len(links)} jobs to Redis...")

    self.job_ids = []

    for link in links:
        job = scrape_queue.enqueue(
            "worker.scrape_job",
            link,
            task['fields'],
            job_timeout=120,
            result_ttl=3600
        )

        self.job_ids.append(job.id)

    self.total_jobs = len(self.job_ids)
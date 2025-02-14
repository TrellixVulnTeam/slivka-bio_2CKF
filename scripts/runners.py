import os
import re
from typing import List
import requests
import tarfile

from slivka.scheduler.runner import BaseCommandRunner, Command, Job

from slivka.utils import JobStatus


class JPredRunner(BaseCommandRunner):
    _jpred4="http://www.compbio.dundee.ac.uk/jpred4"
    _host = "http://www.compbio.dundee.ac.uk/jpred4/cgi-bin/rest"

    def start_one(self, command: Command) -> Job:
        cmd, cwd, _env = command
        with open(cmd[-1]) as fp:
            seq = fp.read()
        content = str.join("£€£€", [*cmd[1:-1], seq])
        response = requests.post(
            '%s/job' % self._host,
            data=content.encode(),
            headers={'Content-type': 'text/txt'}
        )
        response.raise_for_status()
        result_url = response.headers['Location']
        with open(os.path.join(cwd, 'stdout'), 'wb') as fp:
            fp.write(response.content)
        try:
            job_id = re.search(r'jp_.*$', result_url).group()
        except AttributeError:
            raise OSError("Server did not return job id")
        return Job(job_id, cwd)

    def start(self, commands: List[Command]) -> List[Job]:
        return list(map(self.start_one, commands))

    def status_one(self, job: Job) -> JobStatus:
        job_id, cwd = job
        tarball = os.path.join(cwd, 'result.tar.gz')
        if os.path.exists(tarball):
            return JobStatus.COMPLETED
        response = requests.get('%s/job/id/%s' % (self._host, job_id))
        response.raise_for_status()
        if "finished" not in response.text:
            return JobStatus.RUNNING
        archive_url = '{0}/results/{1}/{1}.tar.gz'.format(self._jpred4, job_id)
        arch_response = requests.get(archive_url, stream=True)
        arch_response.raise_for_status()
        with open(tarball, 'wb') as fp:
            for chunk in arch_response.iter_content(chunk_size=4096):
                fp.write(chunk)
        with tarfile.open(tarball) as archive:
            def is_within_directory(directory, target):
                
                abs_directory = os.path.abspath(directory)
                abs_target = os.path.abspath(target)
            
                prefix = os.path.commonprefix([abs_directory, abs_target])
                
                return prefix == abs_directory
            
            def safe_extract(tar, path=".", members=None, *, numeric_owner=False):
            
                for member in tar.getmembers():
                    member_path = os.path.join(path, member.name)
                    if not is_within_directory(path, member_path):
                        raise Exception("Attempted Path Traversal in Tar File")
            
                tar.extractall(path, members, numeric_owner=numeric_owner) 
                
            
            safe_extract(archive, cwd)
        return JobStatus.COMPLETED

    def status(self, jobs: List[Job]) -> List[JobStatus]:
        return list(map(self.status_one, jobs))

    def cancel(self, jobs: List[Job]):
        pass